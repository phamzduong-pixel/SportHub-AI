from types import SimpleNamespace
from unittest.mock import patch

import pytest

from app.schemas.ai import AssistantMode
from app.services.ai_assistant_service import AIAssistantService
from app.services.ai_domain_policy import ScopeClassification


def _service(user=None):
    repository = SimpleNamespace(db=None, scope_for_user=lambda _user: None)
    return AIAssistantService(repository, current_user=user, guardrail=SimpleNamespace())


@pytest.mark.parametrize('question', [
    'Bạn biết tôi tên là gì không?',
    'Tên của tôi là gì?',
    'Bạn có nhớ tên của tôi không?',
    'Bạn có biết tên của tôi không?',
])
def test_natural_mode_uses_authenticated_account_name(question):
    user = SimpleNamespace(id=1, role='CUSTOMER', full_name='Nguyễn Văn A')
    service = _service(user)
    with patch('app.services.ai_assistant_service.get_llm_sports_processor', side_effect=AssertionError('provider used')):
        response = service.ask(question, assistant_mode=AssistantMode.NATURAL)

    assert response['reply'] == 'Tên trong hồ sơ SportHub của bạn là Nguyễn Văn A.'
    assert response['intent'] == 'ACCOUNT_SUPPORT'
    assert response['classification'] == ScopeClassification.IN_SCOPE.value
    assert response['status'] == 'OK'


@pytest.mark.parametrize('user', [
    None,
    SimpleNamespace(id=2, role='CUSTOMER', full_name='   '),
])
def test_natural_mode_does_not_guess_missing_account_name(user):
    response = _service(user).ask('Tôi tên là gì?', assistant_mode=AssistantMode.NATURAL)

    assert response['intent'] == 'ACCOUNT_SUPPORT'
    assert response['classification'] == ScopeClassification.IN_SCOPE.value
    assert 'chưa biết tên' in response['reply']
    assert 'Bạn muốn mình gọi bạn là gì?' in response['reply']


def test_account_name_does_not_leak_between_users_or_use_stale_route():
    first = _service(SimpleNamespace(id=1, role='CUSTOMER', full_name='Nguyễn Văn A'))
    second = _service(SimpleNamespace(id=2, role='CUSTOMER', full_name='Trần Thị B'))

    first.ask('Bạn khỏe không?', assistant_mode=AssistantMode.NATURAL)
    first_response = first.ask('Tên tôi là gì?', assistant_mode=AssistantMode.NATURAL)
    second_response = second.ask('Tên tôi là gì?', assistant_mode=AssistantMode.NATURAL)

    assert 'Nguyễn Văn A' in first_response['reply']
    assert 'Nguyễn Văn A' not in second_response['reply']
    assert 'Trần Thị B' in second_response['reply']
    assert second_response['intent'] == 'ACCOUNT_SUPPORT'


def test_name_of_sports_entity_is_not_treated_as_account_name():
    service = _service(SimpleNamespace(id=1, role='CUSTOMER', full_name='Nguyễn Văn A'))

    assert service._answer_account_name_question('Tên của Messi là gì?') is None
    assert service._answer_account_name_question('Tên sân của tôi là gì?') is None


def test_natural_social_and_ai_identity_questions_keep_their_existing_routes():
    service = _service(SimpleNamespace(id=1, role='CUSTOMER', full_name='Nguyễn Văn A'))

    social = service.ask('Bạn khỏe không?', assistant_mode=AssistantMode.NATURAL)
    identity = service.ask('Bạn tên gì?', assistant_mode=AssistantMode.NATURAL)

    assert social['intent'] == 'CASUAL'
    assert identity['intent'] == 'AI_IDENTITY'
    assert 'Nguyễn Văn A' not in identity['reply']


def test_professional_mode_does_not_use_natural_account_name_branch():
    service = _service(SimpleNamespace(id=1, role='CUSTOMER', full_name='Nguyễn Văn A'))

    response = service.ask('Bạn biết tôi tên là gì không?', assistant_mode=AssistantMode.PROFESSIONAL)

    assert 'Nguyễn Văn A' not in response['reply']
    assert response['status'] == 'OUT_OF_SCOPE'
