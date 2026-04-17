from __future__ import annotations

from typing import Any, Dict, Tuple

from .ai_live_chat import generate_intro_message, generate_live_next_turn
from .clarification_flow import guidance_from_answers
from .models import UploadClarificationResponse, UploadConversationSession, UploadConversationTurn


QUESTION_LABELS = {
    'primary_goal': 'your main goal',
    'main_measures': 'the most important numbers',
    'target_column': 'whether target comparisons matter',
    'time_axis': 'the time story',
    'important_dimensions': 'the most useful breakdowns',
    'output_mode': 'the dashboard style',
    'business_context': 'any special business focus',
}


def _display_name(user) -> str:
    for attr in ('first_name', 'name'):
        value = getattr(user, attr, '') or ''
        if str(value).strip():
            return str(value).strip().split()[0]
    username = getattr(user, 'username', '') or ''
    if username:
        return username.split('@')[0]
    return 'there'


def _question_type(question: Dict[str, Any]) -> str:
    q_type = question.get('type')
    if q_type == 'single_select':
        choices = question.get('choices') or []
        values = {str(c.get('value')) for c in choices if isinstance(c, dict)}
        if values == {'Yes', 'No'} or values == {'yes', 'no'}:
            return 'yes_no'
        return 'single_choice'
    if q_type == 'multi_select':
        return 'multi_choice'
    return 'text'


def build_chat_question(question: Dict[str, Any], profile: Dict[str, Any]) -> Dict[str, Any]:
    chat_question = dict(question)
    chat_question['chat_type'] = _question_type(question)
    chat_question['friendly_help_text'] = question.get('helper') or question.get('help_text') or ''
    chat_question['allow_skip'] = question.get('allow_skip', True)
    chat_question['allow_dont_know'] = bool(question.get('allow_dont_know', False))
    return chat_question


def _ensure_turn(session: UploadConversationSession, role: str, kind: str, message: str, **kwargs):
    existing = session.turns.filter(role=role, kind=kind, message=message, question_key=kwargs.get('question_key', '')).first()
    if existing:
        return existing
    return UploadConversationTurn.objects.create(session=session, role=role, kind=kind, message=message, **kwargs)


def _compute_confidence(profile_obj, answers: Dict[str, Any]) -> Dict[str, float]:
    profile = profile_obj.profile_json or {}
    has_goal = bool(answers.get('primary_goal'))
    has_measure = bool(answers.get('main_measures'))
    has_dim = bool(answers.get('important_dimensions'))
    target_needed = bool(profile.get('target_columns'))
    time_needed = bool(profile.get('time_columns'))
    target_ok = (not target_needed) or bool(str(answers.get('target_column', '')).strip())
    time_ok = (not time_needed) or bool(str(answers.get('time_axis', '')).strip())
    output_ok = bool(str(answers.get('output_mode', '')).strip())
    business_ok = bool(str(answers.get('business_context', '')).strip())

    confidence = {
        'primary_goal_confidence': 1.0 if has_goal else 0.25,
        'measure_mapping_confidence': 1.0 if has_measure else 0.35,
        'dimension_confidence': 1.0 if has_dim else 0.35,
        'target_mapping_confidence': 1.0 if target_ok else 0.4,
        'time_axis_confidence': 1.0 if time_ok else 0.4,
        'output_mode_confidence': 1.0 if output_ok else 0.5,
        'context_confidence': 1.0 if business_ok else 0.55,
    }
    weights = {
        'primary_goal_confidence': 0.2,
        'measure_mapping_confidence': 0.2,
        'dimension_confidence': 0.17,
        'target_mapping_confidence': 0.15,
        'time_axis_confidence': 0.15,
        'output_mode_confidence': 0.08,
        'context_confidence': 0.05,
    }
    readiness = sum(confidence[k] * weights[k] for k in weights)
    confidence['chart_readiness_score'] = round(readiness, 3)
    return confidence


def build_business_brief(profile_obj, answers: Dict[str, Any]) -> Dict[str, Any]:
    guidance = guidance_from_answers(answers)
    goals = guidance.get('primary_goals') or []
    profile = profile_obj.profile_json or {}
    brief = {
        'summary': 'Conversation-guided dashboard brief',
        'main_objective': goals[0] if goals else 'General decision support',
        'all_objectives': goals,
        'priority_measures': guidance.get('priority_measures') or [],
        'priority_dimensions': guidance.get('priority_dimensions') or [],
        'target_column': guidance.get('target_column') or '',
        'time_column': guidance.get('time_column') or '',
        'output_mode': guidance.get('output_mode') or 'Full analytical dashboard',
        'business_context': guidance.get('business_context') or '',
        'likely_analysis_type': ((profile_obj.screening_json or {}).get('analysis_type') or ''),
        'recommended_focus': (profile_obj.screening_json or {}).get('recommended_focus') or [],
        'profile_measures': profile.get('measures') or [],
        'profile_dimensions': profile.get('dimensions') or [],
    }
    return brief


def get_or_create_session(profile_obj, user=None) -> UploadConversationSession:
    session, created = UploadConversationSession.objects.get_or_create(profile=profile_obj)
    if created or not session.turns.exists():
        session.meta_json = session.meta_json or {}
        session.meta_json['conversation_mode'] = 'live_ai_chat'
        session.meta_json['current_question'] = None
        session.save(update_fields=['meta_json', 'updated_at'])
        opening = generate_intro_message(profile_obj.profile_json or {}, user=user)
        _ensure_turn(session, 'assistant', 'message', opening)
    return session


def sync_session(profile_obj, answers: Dict[str, Any], user=None) -> Tuple[UploadConversationSession, Dict[str, Any]]:
    session = get_or_create_session(profile_obj, user=user)
    confidence = _compute_confidence(profile_obj, answers)
    brief = build_business_brief(profile_obj, answers)
    live_turn = generate_live_next_turn(session, profile_obj, answers, user=user)

    review_state: Dict[str, Any] = {
        'selection_source': live_turn.get('source', 'live'),
        'answered_count': sum(1 for value in answers.values() if (bool(value) if not isinstance(value, str) else bool(value.strip()))),
        'total_questions': 7,
    }

    if live_turn.get('done') or confidence['chart_readiness_score'] >= 0.86:
        session.status = UploadConversationSession.STATUS_READY
        session.current_question_key = ''
        session.meta_json = {**(session.meta_json or {}), 'current_question': None, 'conversation_mode': 'live_ai_chat'}
        completion_message = live_turn.get('message') or 'Perfect — I have enough. I’ll build the dashboard around that.'
        _ensure_turn(session, 'assistant', 'message', completion_message)
        review_state['chat_question'] = None
        review_state['is_complete'] = True
    else:
        current = build_chat_question(live_turn['question'], profile_obj.profile_json or {})
        session.status = UploadConversationSession.STATUS_ACTIVE
        session.current_question_key = current.get('key') or ''
        session.meta_json = {**(session.meta_json or {}), 'current_question': current, 'conversation_mode': 'live_ai_chat'}
        _ensure_turn(
            session,
            'assistant',
            'question',
            current.get('prompt') or '',
            question_key=current.get('key', ''),
            question_type=current.get('chat_type', ''),
            meta_json=current,
        )
        review_state['chat_question'] = current
        review_state['is_complete'] = False

    session.readiness_score = confidence['chart_readiness_score']
    session.confidence_json = confidence
    session.brief_json = brief
    session.save(update_fields=['status', 'current_question_key', 'readiness_score', 'confidence_json', 'brief_json', 'meta_json', 'updated_at'])

    review_state['conversation_turns'] = list(session.turns.all())
    review_state['confidence'] = confidence
    review_state['confidence_percentages'] = {k: int(round(v * 100)) for k, v in confidence.items()}
    review_state['business_brief'] = brief
    review_state['ready_to_build'] = session.status == UploadConversationSession.STATUS_READY
    return session, review_state



def _normalise_answer_for_question(question: Dict[str, Any], request_post) -> Tuple[Any, str]:
    key = question.get('key')
    q_type = question.get('type')
    choices = question.get('choices') or []
    choice_map = {str(c.get('value')): str(c.get('label') or c.get('value')) for c in choices if isinstance(c, dict)}

    if q_type == 'multi_select':
        values = request_post.getlist(key)
        max_select = int(question.get('max_select') or 0)
        values = values[:max_select] if max_select else values
        labels = [choice_map.get(str(v), str(v)) for v in values]
        return values, ', '.join(labels)

    value = request_post.get(key, '')
    return value, choice_map.get(str(value), str(value))



def save_turn_answer(profile_obj, request, answers: Dict[str, Any], user=None) -> Tuple[UploadConversationSession, Dict[str, Any], Dict[str, Any]]:
    session = get_or_create_session(profile_obj, user=user)
    question = ((session.meta_json or {}).get('current_question') or {})
    active_key = request.POST.get('active_key', '').strip() or question.get('key', '')
    action = request.POST.get('action', 'next')
    prev_conf = _compute_confidence(profile_obj, answers).get('chart_readiness_score', 0)

    if question and active_key == question.get('key') and action == 'dont_know':
        answers[active_key] = ''
        label = "Don't know"
        UploadConversationTurn.objects.create(session=session, role='user', kind='answer', question_key=active_key, question_type=_question_type(question), message=label, answer_value_json={'value': ''}, answer_label=label, dont_know=True, confidence_before=prev_conf, confidence_after=prev_conf)
    elif question and active_key == question.get('key') and action == 'skip':
        answers.setdefault(active_key, [] if question.get('type') == 'multi_select' else '')
        label = 'Skip'
        UploadConversationTurn.objects.create(session=session, role='user', kind='answer', question_key=active_key, question_type=_question_type(question), message=label, answer_value_json={'value': answers.get(active_key)}, answer_label=label, skipped=True, confidence_before=prev_conf, confidence_after=prev_conf)
    elif question and active_key == question.get('key'):
        value, label = _normalise_answer_for_question(question, request.POST)
        if action == 'finish' and (value in ('', [], None)):
            label = ''
        else:
            answers[active_key] = value
            after_guidance = guidance_from_answers(answers)
            after_conf = _compute_confidence(profile_obj, answers).get('chart_readiness_score', prev_conf)
            UploadConversationTurn.objects.create(session=session, role='user', kind='answer', question_key=active_key, question_type=_question_type(question), message=str(label), answer_value_json={'value': value}, answer_label=label, confidence_before=prev_conf, confidence_after=after_conf, meta_json={'guidance_preview': after_guidance})

    guidance = guidance_from_answers(answers)
    UploadClarificationResponse.objects.update_or_create(profile=profile_obj, defaults={'response_json': answers, 'guidance_json': guidance})
    session, review_state = sync_session(profile_obj, answers, user=user)
    return session, review_state, guidance
