import unittest
from unittest.mock import patch

import httpx

from app.core.config import settings
from app.services.ai_provider import AIProviderError, OpenAIProvider


class FakeResponse:
    def __init__(self, content):
        self.content = content

    def raise_for_status(self):
        return None

    def json(self):
        return {'choices': [{'message': {'content': self.content}}]}


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


if __name__ == '__main__':
    unittest.main()
