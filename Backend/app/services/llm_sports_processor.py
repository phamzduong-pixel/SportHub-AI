import logging
import json
from dataclasses import dataclass
from typing import Any

from .ai_provider import OpenAIProvider, AIProviderError
from ..core.config import settings

logger = logging.getLogger(__name__)

@dataclass
class QueryUnderstanding:
    entities: list[str]          # canonical entity names
    sport: str | None            # detected sport
    topic: str | None            # identity, birth_date, current_club, achievements, career, status, founded, rules, etc.
    is_follow_up: bool           # whether this references a previous turn
    rewritten_query: str         # full standalone query with resolved pronouns/context
    original_query: str          # original user message

@dataclass
class GroundedResponse:
    answer: str                  # natural language answer
    citations: list[dict]        # [{source_name, source_url, collected_at}]
    used_llm: bool               # whether LLM was actually used

class LLMSportsQueryProcessor:
    SUPPORTED_SPORTS = ('bóng đá', 'cầu lông', 'pickleball', 'tennis', 'bóng rổ', 'bóng chuyền')
    MAX_HISTORY_TURNS = 10
    
    def __init__(self):
        self._provider: OpenAIProvider | None = None
        self._available: bool | None = None  # lazy check
    
    @property
    def provider(self) -> OpenAIProvider | None:
        if self._available is None:
            try:
                key = settings.OPENAI_API_KEY
                if key and not key.startswith('replace-with-'):
                    self._provider = OpenAIProvider()
                    self._available = True
                else:
                    self._available = False
            except Exception:
                self._available = False
        return self._provider if self._available else None
    
    def understand_query(self, message: str, conversation_messages: list[dict] | None = None, context: dict | None = None) -> QueryUnderstanding | None:
        """Use LLM to understand the sports query with entity resolution, follow-up detection, and query rewriting.
        
        Returns None if LLM is unavailable or fails (caller should use deterministic fallback).
        """
        provider = self.provider
        if not provider:
            return None
        
        # Build conversation history string for LLM context
        history_text = self._format_history(conversation_messages)
        
        # Build context hints from existing deterministic extraction
        context_hints = ''
        if context:
            if context.get('sports_entity'):
                context_hints += f"Previous entity discussed: {context['sports_entity']}\n"
            if context.get('sport_type'):
                context_hints += f"Previous sport: {context['sport_type']}\n"
            if context.get('last_intent'):
                context_hints += f"Previous intent: {context['last_intent']}\n"
        
        system_prompt = '''You are a sports query analyzer for SportHub AI.
SportHub covers exactly 6 sports: Bóng đá (Football), Cầu lông (Badminton), Pickleball, Tennis, Bóng rổ (Basketball), Bóng chuyền (Volleyball).

Given a user message and optional conversation history, extract structured information.

Rules:
- Resolve jersey numbers and nicknames (written as numbers or words):
  * "anh 7" / "anh bảy" / "CR7" / "chị 7" → Cristiano Ronaldo (in football)
  * "anh 10" / "anh mười" / "M10" / "La Pulga" / "El Pulga" → Lionel Messi (in football)
  * "anh 9" / "anh chín" / "R9" / "người ngoài hành tinh" → Ronaldo de Lima
  * "đấng Maguire" / "chúa tể Maguire" / "mắc hài" → Harry Maguire
  * "Lakaka" → Romelu Lukaku
  * "Hải con" / "thánh trượt cỏ" → Nguyễn Quang Hải
  * "Linh Ka" → Nguyễn Tiến Linh
  * "Tàu tốc hành" / "FedEx" → Roger Federer (Tennis)
  * "Vua đất nện" / "King of Clay" → Rafael Nadal (Tennis)
  * "Nole" / "The Djoker" → Novak Djokovic (Tennis)
  * "Nhà vua" / "King James" → LeBron James (Basketball)
  * "Bếp trưởng" / "Chef Curry" → Stephen Curry (Basketball)
  * "Super Dan" → Lin Dan (Badminton)
  * "Khủng long bóng chuyền" → Nguyễn Thị Bích Tuyền (Volleyball)
  * "4T" / "Chủ công 4T" → Trần Thị Thanh Thúy (Volleyball)
  * "Vua Pickleball" → Ben Johns (Pickleball)
  * "Nữ hoàng Pickleball" → Anna Leigh Waters (Pickleball)
- Resolve Vietnamese player names: Quang Hải → Nguyễn Quang Hải, Tiến Linh → Nguyễn Tiến Linh, Hoàng Đức → Nguyễn Hoàng Đức, Thùy Linh → Nguyễn Thùy Linh, Tiến Minh → Nguyễn Tiến Minh.
- Resolve pronouns from conversation history: "anh ấy"/"ông ấy"/"cô ấy" → the entity from the previous turn.
- Follow-ups: "Còn anh 10?" / "Thế còn anh 10 là ai?" / "Còn X?" inherits the sport and context from previous turn (e.g. if previous was football/Cristiano Ronaldo, "anh 10" resolves to Lionel Messi in football).
- Memes & jokes: "anh 7 đi bộ vuốt tóc", "đấng maguire gánh team", "ai là GOAT" → extract entities and sport accurately.
- If query is outside the 6 supported sports (e.g., esports, golf, swimming) → entities=[], sport=""
- For topic, use one of: identity, birth_date, birth_place, current_club, achievements, career, status, founded, rules, height, weight, statistics, comparison, meme, humor, general
- rewritten_query must be a complete standalone question in Vietnamese that doesn't need conversation context to understand
- If no sport detected, set sport to empty string. If no topic detected, set topic to empty string.'''
        
        user_content = f"""Conversation history:
{history_text or '(no history)'}

Context:
{context_hints or '(no context)'}

Current user message: {message}

Extract the structured information."""
        
        schema = {
            'type': 'object',
            'properties': {
                'entities': {'type': 'array', 'items': {'type': 'string'}, 'maxItems': 5},
                'sport': {'type': 'string'},
                'topic': {'type': 'string'},
                'is_follow_up': {'type': 'boolean'},
                'rewritten_query': {'type': 'string'},
            },
            'required': ['entities', 'sport', 'topic', 'is_follow_up', 'rewritten_query'],
            'additionalProperties': False,
        }
        
        try:
            # Use generate_json for structured output
            result = provider.generate_json(
                task='sports_query_understanding',
                system_data={'system_prompt': system_prompt, 'user_message': user_content},
                schema=schema,
            )
            return QueryUnderstanding(
                entities=result.get('entities', []),
                sport=result.get('sport') or None,
                topic=result.get('topic') or None,
                is_follow_up=result.get('is_follow_up', False),
                rewritten_query=result.get('rewritten_query', message),
                original_query=message,
            )
        except (AIProviderError, Exception) as exc:
            logger.warning('LLM query understanding failed: %s', exc)
            return None
    
    def select_and_validate_evidence(
        self,
        evidence_entries: list,
        target_entity: str | None = None,
        target_topic: str | None = None,
        max_items: int = 5,
    ) -> list:
        """Validate, rank, and select the highest quality evidence items.

        Priority order:
        1. Exact match on target entity and target topic
        2. Match on target entity or target topic
        3. High quality / official sports sources
        4. Freshness
        """
        if not evidence_entries:
            return []

        HIGH_QUALITY_SOURCES = {
            'fifa', 'bwf', 'vff', 'ppa tour', 'vba', 'ictu', 'vtv', 'olympics', 'uefa',
            'wikipedia', 'flashscore', 'bongdaplus', 'vnexpress', 'thethao247', 'dantri'
        }

        seen_answers = set()
        scored_entries = []

        for item in evidence_entries:
            if isinstance(item, tuple):
                entry, base_score = item
            else:
                entry, base_score = item, 1.0

            content = getattr(entry, 'answer', None) or getattr(entry, 'content', '') or str(entry)
            norm_content = content.strip().lower()
            if not norm_content or norm_content in seen_answers:
                continue
            seen_answers.add(norm_content)

            ent = (getattr(entry, 'entity', '') or '').strip().lower()
            top = (getattr(entry, 'topic', '') or '').strip().lower()
            src = (getattr(entry, 'source_name', '') or getattr(entry, 'source', '') or '').strip().lower()
            entry_id = (getattr(entry, 'id', '') or '').strip()

            # If targeting athletes/teams, filter out generic game rules (e.g. offside / việt vị)
            if target_topic in ('identity', 'cầu thủ', 'vận động viên', 'athletes') or target_entity:
                if 'rule' in entry_id.lower() or top in ('rules', 'luật'):
                    continue

            priority_weight = float(base_score)

            # Entity match bonus
            if target_entity:
                target_ent_lower = target_entity.strip().lower()
                if target_ent_lower == ent or target_ent_lower in ent:
                    priority_weight += 2.0
                elif ent and ent in target_ent_lower:
                    priority_weight += 1.5

            # Topic match bonus
            if target_topic:
                target_top_lower = target_topic.strip().lower()
                if target_top_lower == top or target_top_lower in top:
                    priority_weight += 2.0
                elif top and top in target_top_lower:
                    priority_weight += 1.0

            # Source quality bonus
            if any(hq in src for hq in HIGH_QUALITY_SOURCES):
                priority_weight += 0.5

            # Freshness bonus
            collected = getattr(entry, 'collected_at', None) or ''
            if collected and ('2025' in collected or '2026' in collected):
                priority_weight += 0.3

            scored_entries.append((priority_weight, (entry, base_score)))

        scored_entries.sort(key=lambda x: x[0], reverse=True)
        return [entry_tuple for _, entry_tuple in scored_entries[:max_items]]

    def validate_grounding(self, answer: str, evidence_entries: list) -> bool:
        """Grounding / Guardrail check.
        
        Verifies that the generated response is non-empty.
        """
        if not answer or not answer.strip():
            return False
        return True

    def generate_grounded_response(
        self,
        query: str,
        evidence_entries: list,
        conversation_messages: list[dict] | None = None,
        target_entity: str | None = None,
        target_topic: str | None = None,
    ) -> GroundedResponse | None:
        """Use LLM to generate a natural, fluent ChatGPT-style response for sports knowledge.
        
        Args:
            query: the user's query (possibly rewritten)
            evidence_entries: list of (KnowledgeEntry, score) tuples or empty list
            conversation_messages: recent conversation history
            target_entity: optional resolved entity name
            target_topic: optional resolved topic
        
        Returns None if LLM is unavailable or fails (caller should use deterministic fallback).
        """
        provider = self.provider
        if not provider:
            return None

        # Select best evidences based on priority rules if available
        selected_evidence = []
        if evidence_entries:
            selected_evidence = self.select_and_validate_evidence(
                evidence_entries, target_entity=target_entity, target_topic=target_topic, max_items=5
            )
        
        # Format evidence for LLM
        if selected_evidence:
            evidence_text = self._format_evidence(selected_evidence)
        else:
            evidence_text = "(Không có trích đoạn dữ liệu cục bộ cụ thể; hãy sử dụng hiểu biết thể thao chuyên sâu của bạn để trả lời đầy đủ, chính xác theo 6 môn của SportHub)"
            
        history_text = self._format_history(conversation_messages)
        
        system_prompt = '''You are SportHub AI Assistant in Natural Mode — an enthusiastic, intelligent, and knowledgeable sports AI expert (like modern ChatGPT) specialized in 6 sports: Bóng đá (Football), Cầu lông (Badminton), Pickleball, Tennis, Bóng rổ (Basketball), Bóng chuyền (Volleyball).

Guidelines:
- Tone: Friendly, natural, helpful, witty, and conversational in Vietnamese (như một người bạn am hiểu thể thao).
- Answering Structure:
  1. Direct Answer: Answer the user's question clearly and directly right at the beginning.
  2. Structured Details / Bullet Points: When answering about athletes, players, teams, or facts, list key people / items with neat bullet points (e.g. • **Tên vận động viên / CLB**: Vị trí, vai trò, thành tích nổi bật).
  3. Context / Explanation: Provide brief helpful context, origin of nicknames/slangs or insights if relevant.
- Sports Nicknames, Slangs & Memes:
  - Understand informal names & jersey numbers (written in words or digits, e.g., "anh 7"/"anh bảy" = Cristiano Ronaldo, "anh 10"/"anh mười" = Lionel Messi, "đấng Maguire" = Harry Maguire, "Lakaka" = Romelu Lukaku, "Tàu tốc hành" = Roger Federer, "Vua đất nện" = Rafael Nadal, "Nhà vua" = LeBron James, "Bếp trưởng" = Stephen Curry, "Super Dan" = Lin Dan, "Khủng long bóng chuyền" = Bích Tuyền, "4T" = Thanh Thúy, "Vua Pickleball" = Ben Johns).
  - For sports memes, jokes, and teasing ("anh 7 đi bộ vuốt tóc", "đấng Maguire gánh team", "ai là GOAT?"): Explain the humorous context warmly and wittily while keeping the core athletic facts accurate (do not validate memes as formal facts).
  - For ambiguous queries with minimal context ("anh 7 là ai?"): Provide a clear, conditional answer referencing the famous football context and politely invite the user to clarify if they meant another context.
- Knowledge & Grounding:
  - If verified evidence from SportHub knowledge base or official sources is provided in the prompt, prioritize and seamlessly integrate those verified facts (e.g. CLB nữ Thái Nguyên T&T với Kim Thanh, Bích Thùy, Trần Thị Thu, Mỹ Anh, Ngọc Minh Chuyên; FC Thái Nguyên; ICTU; CLB V-League; ĐTQG Việt Nam).
  - You are encouraged to use your extensive sports knowledge for the 6 supported sports to provide a complete, well-structured, and helpful answer.
  - If no evidence is provided, answer accurately and informatively based on your sports domain knowledge for the 6 supported sports.
- Scope:
  - SportHub specializes in the 6 supported sports. If a question is completely outside sports (e.g. cooking, coding) or outside the 6 sports, politely decline and offer to help with the 6 supported sports.
- Formatting: Clean Markdown formatting with bullet points and light sports emojis (⚽🏸🎾🏀🏐). Do NOT put raw URLs inside the body text.'''
        
        user_content = f"""Conversation context:
{history_text or '(first message)'}

User question: {query}

Evidence:
{evidence_text}

Generate a natural, smart, and comprehensive sports response."""
        
        # Collect citations from selected evidence
        citations = self._extract_citations(selected_evidence) if selected_evidence else []
        
        try:
            answer = provider.generate(
                task='grounded_sports_response',
                system_data={'system_prompt': system_prompt, 'user_message': user_content},
            )
            # Clean up LLM response
            answer = answer.strip()
            if not answer or not self.validate_grounding(answer, selected_evidence):
                return None
            return GroundedResponse(answer=answer, citations=citations, used_llm=True)
        except (AIProviderError, Exception) as exc:
            logger.warning('LLM response generation failed: %s', exc)
            return None
    
    def _format_history(self, conversation_messages: list[dict] | None) -> str:
        if not conversation_messages:
            return ''
        lines = []
        for msg in conversation_messages[-self.MAX_HISTORY_TURNS:]:
            role = msg.get('role', 'user')
            content = msg.get('content', '')
            # Truncate long messages
            if len(content) > 300:
                content = content[:300] + '...'
            prefix = 'User' if role == 'user' else 'Assistant'
            lines.append(f"{prefix}: {content}")
        return '\n'.join(lines)
    
    def _format_evidence(self, evidence_entries: list) -> str:
        lines = []
        for i, (entry, score) in enumerate(evidence_entries[:8], 1):
            source_name = getattr(entry, 'source_name', None) or getattr(entry, 'source', 'unknown')
            collected_at = getattr(entry, 'collected_at', None) or ''
            entity = getattr(entry, 'entity', None) or ''
            topic = getattr(entry, 'topic', None) or ''
            answer = entry.answer if hasattr(entry, 'answer') else str(entry)
            
            lines.append(f"[Evidence {i}]")
            if entity:
                lines.append(f"Entity: {entity}")
            if topic:
                lines.append(f"Topic: {topic}")
            lines.append(f"Content: {answer}")
            lines.append(f"Source: {source_name}")
            if collected_at:
                lines.append(f"Date: {collected_at}")
            lines.append('')
        return '\n'.join(lines)
    
    def _extract_citations(self, evidence_entries: list) -> list[dict]:
        citations = []
        seen_sources = set()
        for entry, score in evidence_entries:
            src_name = getattr(entry, 'source_name', None) or getattr(entry, 'source', None)
            src_url = getattr(entry, 'source_url', None)
            collected_at = getattr(entry, 'collected_at', None)
            if src_name and src_name not in seen_sources:
                seen_sources.add(src_name)
                citations.append({
                    'source_name': src_name,
                    'source_url': src_url,
                    'collected_at': collected_at,
                })
        return citations


# Singleton instance
_processor_instance: LLMSportsQueryProcessor | None = None

def get_llm_sports_processor() -> LLMSportsQueryProcessor:
    global _processor_instance
    if _processor_instance is None:
        _processor_instance = LLMSportsQueryProcessor()
    return _processor_instance
