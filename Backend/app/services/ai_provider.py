import json
import logging
from abc import ABC, abstractmethod
from time import sleep
from typing import Any

import httpx

from ..core.config import settings

logger = logging.getLogger(__name__)


class AIProviderError(RuntimeError):
    pass


SYSTEM_RULES = """You are SportHub AI. Use only the supplied system_data.
Never invent or modify courts, slots, prices, availability, bookings, payments, or analytics.
For slot recommendations, choose only court_id and slot_id pairs in available_slots.
If required input is missing return NEED_MORE_DATA. If available_slots is empty return NO_AVAILABLE_SLOT.
Never claim that you changed a price or created a promotion. Return only the requested format."""


class AIProvider(ABC):
    @abstractmethod
    def generate(self, *, task: str, system_data: dict) -> str:
        raise NotImplementedError

    @abstractmethod
    def generate_json(self, *, task: str, system_data: dict, schema: dict) -> dict:
        raise NotImplementedError


class OpenAIProvider(AIProvider):
    """Provider adapter. It never logs credentials, prompts, or system business data."""

    endpoint = 'https://api.openai.com/v1/chat/completions'

    def generate(self, *, task: str, system_data: dict) -> str:
        payload = self._payload(task, system_data)
        return self._request(payload, task)

    def generate_json(self, *, task: str, system_data: dict, schema: dict) -> dict:
        payload = self._payload(task, system_data)
        payload['response_format'] = {
            'type': 'json_schema',
            'json_schema': {'name': task, 'strict': True, 'schema': schema},
        }
        content = self._request(payload, task)
        try:
            result = json.loads(content)
        except (TypeError, ValueError, json.JSONDecodeError) as error:
            raise AIProviderError('AI provider returned invalid JSON') from error
        self._validate_schema(result, schema)
        return result

    @staticmethod
    def _payload(task: str, system_data: dict) -> dict:
        return {
            'model': settings.OPENAI_MODEL,
            'messages': [
                {'role': 'system', 'content': SYSTEM_RULES},
                {'role': 'user', 'content': json.dumps(
                    {'task': task, 'system_data': system_data}, ensure_ascii=False, default=str,
                )},
            ],
        }

    def _request(self, payload: dict, task: str) -> str:
        if not settings.OPENAI_API_KEY or settings.OPENAI_API_KEY.startswith('replace-with-'):
            raise AIProviderError('AI provider is not configured')
        retries = max(0, int(getattr(settings, 'AI_PROVIDER_MAX_RETRIES', 1)))
        for attempt in range(retries + 1):
            try:
                with httpx.Client(timeout=settings.AI_PROVIDER_TIMEOUT_SECONDS) as client:
                    response = client.post(
                        self.endpoint, json=payload,
                        headers={'Authorization': f'Bearer {settings.OPENAI_API_KEY}'},
                    )
                response.raise_for_status()
                content = response.json()['choices'][0]['message']['content']
                if not isinstance(content, str) or not content.strip():
                    raise ValueError('empty provider content')
                return content
            except (httpx.TimeoutException, httpx.TransportError) as error:
                if attempt < retries:
                    sleep(min(0.1 * (attempt + 1), 0.3))
                    continue
                logger.warning('AI provider transport failure task=%s type=%s', task, type(error).__name__)
                raise AIProviderError('AI provider timed out or is unavailable') from error
            except (httpx.HTTPStatusError, KeyError, TypeError, ValueError) as error:
                logger.warning('AI provider response failure task=%s type=%s', task, type(error).__name__)
                raise AIProviderError('AI provider returned an invalid response') from error
        raise AIProviderError('AI provider failed')

    @classmethod
    def _validate_schema(cls, value: Any, schema: dict, path: str = '$') -> None:
        expected = schema.get('type')
        valid = {
            'object': isinstance(value, dict),
            'array': isinstance(value, list),
            'string': isinstance(value, str),
            'integer': isinstance(value, int) and not isinstance(value, bool),
            'number': isinstance(value, (int, float)) and not isinstance(value, bool),
            'boolean': isinstance(value, bool),
        }
        if expected in valid and not valid[expected]:
            raise AIProviderError(f'AI JSON schema mismatch at {path}')
        if 'enum' in schema and value not in schema['enum']:
            raise AIProviderError(f'AI JSON enum mismatch at {path}')
        if expected == 'object':
            required = schema.get('required', [])
            if any(key not in value for key in required):
                raise AIProviderError(f'AI JSON missing required field at {path}')
            properties = schema.get('properties', {})
            if schema.get('additionalProperties') is False and any(key not in properties for key in value):
                raise AIProviderError(f'AI JSON has unknown field at {path}')
            for key, item in value.items():
                if key in properties:
                    cls._validate_schema(item, properties[key], f'{path}.{key}')
        elif expected == 'array':
            if 'maxItems' in schema and len(value) > schema['maxItems']:
                raise AIProviderError(f'AI JSON array is too long at {path}')
            item_schema = schema.get('items')
            if item_schema:
                for index, item in enumerate(value):
                    cls._validate_schema(item, item_schema, f'{path}[{index}]')


# Compatibility alias for existing imports and deployments.
StructuredAIProvider = OpenAIProvider
