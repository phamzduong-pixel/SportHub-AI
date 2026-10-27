import unittest
from unittest.mock import patch

import httpx

from app.core.config import settings
from app.services.ai_provider import AIProviderError, GeminiTextProvider, OpenAIProvider


class FakeResponse:
    def __init__(self, content):
        self.content = content

    def raise_for_status(self):
        return None

    def json(self):
        return {'choices': [{'message': {'content': self.content}}]}


class FakeGeminiResponse:
    def raise_for_status(self):
        return None

    def json(self):
        return {'candidates': [{'content': {'parts': [{'text': 'Lionel Messi là cầu thủ bóng đá.'}]}}]}


class AIProviderTests(unittest.TestCase):
    schema = {
        'type': 'object', 'additionalProperties': False,
        'properties': {'summary': {'type': 'string'}}, 'required': ['summary'],
    }

    def test_invalid_ai_json_is_rejected(self):
        with patch.object(settings, 'OPENAI_API_KEY', 'test-key'), \
             patch.object(settings, 'AI_PROVIDER_MAX_RETRIES', 0), \
             patch('httpx.Client.post', return_value=FakeResponse('not-json')):
            with self.assertRaises(AIProviderError):
                OpenAIProvider().generate_json(task='invalid_json', system_data={}, schema=self.schema)

    def test_schema_invalid_ai_json_is_rejected(self):
        with patch.object(settings, 'OPENAI_API_KEY', 'test-key'), \
             patch.object(settings, 'AI_PROVIDER_MAX_RETRIES', 0), \
             patch('httpx.Client.post', return_value=FakeResponse('{"unknown":"value"}')):
            with self.assertRaises(AIProviderError):
                OpenAIProvider().generate_json(task='invalid_schema', system_data={}, schema=self.schema)

    def test_provider_timeout_is_wrapped_without_sensitive_logging(self):
        with patch.object(settings, 'OPENAI_API_KEY', 'test-key'), \
             patch.object(settings, 'AI_PROVIDER_MAX_RETRIES', 1), \
             patch('httpx.Client.post', side_effect=httpx.TimeoutException('timeout')) as request:
            with self.assertRaises(AIProviderError):
                OpenAIProvider().generate_json(task='timeout', system_data={'private': 'hidden'}, schema=self.schema)
        self.assertEqual(request.call_count, 2)

    def test_gemini_text_provider_uses_configured_model_and_api_key_header(self):
        with patch.object(settings, 'GEMINI_API_KEY', 'test-gemini-key'), \
             patch.object(settings, 'GEMINI_MODEL', 'gemini-test-flash'), \
             patch('httpx.Client.post', return_value=FakeGeminiResponse()) as request:
            answer = GeminiTextProvider().generate(
                task='background_sports_answer',
                system_data={'system_prompt': 'Hãy trả lời bằng tiếng Việt.', 'user_message': 'Messi là ai?'},
            )

        self.assertEqual(answer, 'Lionel Messi là cầu thủ bóng đá.')
        args, kwargs = request.call_args
        self.assertEqual(args[0], 'https://generativelanguage.googleapis.com/v1beta/models/gemini-test-flash:generateContent')
        self.assertEqual(kwargs['headers'], {'x-goog-api-key': 'test-gemini-key'})
        self.assertEqual(kwargs['json']['contents'][0]['parts'][0]['text'], 'Messi là ai?')

    def test_gemini_provider_without_key_does_not_make_request(self):
        with patch.object(settings, 'GEMINI_API_KEY', None), \
             patch('httpx.Client.post') as request:
            with self.assertRaises(AIProviderError):
                GeminiTextProvider().generate(
                    task='background_sports_answer',
                    system_data={'system_prompt': 'system', 'user_message': 'question'},
                )
        request.assert_not_called()


if __name__ == '__main__':
    unittest.main()
