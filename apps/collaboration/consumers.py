"""
WebSocket consumer for real-time collaboration.
Handles presence (who's viewing), cursor position (tab), and comments.
"""
import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.utils import timezone


class AnalysisConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.user = self.scope['user']
        if not self.user.is_authenticated:
            await self.close()
            return

        self.upload_id  = self.scope['url_route']['kwargs']['upload_id']
        self.room_group = f'analysis_{self.upload_id}'

        # Verify user owns or can view this upload
        allowed = await self._check_permission()
        if not allowed:
            await self.close()
            return

        await self.channel_layer.group_add(self.room_group, self.channel_name)
        await self.accept()
        await self._register_session()

        # Broadcast join
        await self.channel_layer.group_send(self.room_group, {
            'type': 'presence_update',
            'action': 'join',
            'user_id':   self.user.id,
            'user_email': self.user.email,
            'user_initials': self.user.email[0].upper(),
            'tab': 'overview',
        })

        # Send current presence list to the new joiner
        presence = await self._get_presence()
        await self.send(text_data=json.dumps({'type': 'presence_list', 'users': presence}))

    async def disconnect(self, close_code):
        await self._deregister_session()
        await self.channel_layer.group_send(self.room_group, {
            'type': 'presence_update',
            'action': 'leave',
            'user_id': self.user.id,
            'user_email': self.user.email,
        })
        await self.channel_layer.group_discard(self.room_group, self.channel_name)

    async def receive(self, text_data):
        data = json.loads(text_data)
        msg_type = data.get('type')

        if msg_type == 'tab_change':
            tab = data.get('tab', 'overview')
            await self._update_cursor(tab)
            await self.channel_layer.group_send(self.room_group, {
                'type': 'cursor_update',
                'user_id': self.user.id,
                'user_email': self.user.email,
                'tab': tab,
            })

        elif msg_type == 'comment':
            comment = await self._save_comment(data.get('text',''), data.get('tab','overview'), data.get('column_ref',''))
            await self.channel_layer.group_send(self.room_group, {
                'type': 'new_comment',
                'id':       comment.id,
                'author':   self.user.email,
                'initials': self.user.email[0].upper(),
                'text':     comment.text,
                'tab':      comment.tab,
                'column_ref': comment.column_ref,
                'created_at': comment.created_at.isoformat(),
            })

        elif msg_type == 'ping':
            await self._touch_session()
            await self.send(text_data=json.dumps({'type': 'pong'}))

    # ── Event handlers (called by channel_layer.group_send) ──────────────────

    async def presence_update(self, event):
        await self.send(text_data=json.dumps(event))

    async def cursor_update(self, event):
        await self.send(text_data=json.dumps(event))

    async def new_comment(self, event):
        await self.send(text_data=json.dumps(event))

    # ── DB helpers ─────────────────────────────────────────────────────────────

    @database_sync_to_async
    def _check_permission(self):
        from apps.analyser.models import FileUpload
        return FileUpload.objects.filter(pk=self.upload_id, user=self.user).exists()

    @database_sync_to_async
    def _register_session(self):
        from .models import CollabSession
        CollabSession.objects.update_or_create(
            upload_id=self.upload_id, user=self.user,
            defaults={'channel_name': self.channel_name, 'is_active': True, 'cursor_tab': 'overview'},
        )

    @database_sync_to_async
    def _deregister_session(self):
        from .models import CollabSession
        CollabSession.objects.filter(upload_id=self.upload_id, user=self.user).update(is_active=False)

    @database_sync_to_async
    def _update_cursor(self, tab):
        from .models import CollabSession
        CollabSession.objects.filter(upload_id=self.upload_id, user=self.user).update(cursor_tab=tab)

    @database_sync_to_async
    def _touch_session(self):
        from .models import CollabSession
        CollabSession.objects.filter(upload_id=self.upload_id, user=self.user).update(last_seen=timezone.now())

    @database_sync_to_async
    def _get_presence(self):
        from .models import CollabSession
        from django.utils import timezone
        from datetime import timedelta
        cutoff = timezone.now() - timedelta(minutes=5)
        sessions = CollabSession.objects.filter(
            upload_id=self.upload_id, is_active=True, last_seen__gte=cutoff
        ).select_related('user').exclude(user=self.user)
        return [{'user_id': s.user.id, 'user_email': s.user.email,
                 'initials': s.user.email[0].upper(), 'tab': s.cursor_tab} for s in sessions]

    @database_sync_to_async
    def _save_comment(self, text, tab, column_ref):
        from .models import CollabComment
        return CollabComment.objects.create(
            upload_id=self.upload_id, author=self.user,
            text=text[:1000], tab=tab, column_ref=column_ref,
        )
