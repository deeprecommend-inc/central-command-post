from typing import Dict, Any, List, Optional
import anthropic
import openai
import json
import re

from ..core.config import settings


class SafetyFilter:
    """Safety filter for content moderation"""

    def __init__(self, ng_words: List[str] = None):
        self.ng_words = ng_words or []
        self.default_ng_patterns = [
            r'\b(spam|scam|fraud)\b',
            r'\b(hate|harassment)\b',
        ]

    def check_content(self, content: str) -> tuple[bool, List[str]]:
        """
        Check if content passes safety filter
        Returns: (is_safe, violations)
        """
        violations = []

        # Check NG words
        content_lower = content.lower()
        for word in self.ng_words:
            if word.lower() in content_lower:
                violations.append(f"NG word detected: {word}")

        # Check default patterns
        for pattern in self.default_ng_patterns:
            if re.search(pattern, content_lower, re.IGNORECASE):
                violations.append(f"Prohibited pattern detected: {pattern}")

        return len(violations) == 0, violations


class DuplicationChecker:
    """Check content duplication rate"""

    def __init__(self, previous_contents: List[str] = None):
        self.previous_contents = previous_contents or []

    def calculate_similarity(self, text1: str, text2: str) -> float:
        """Calculate similarity between two texts (simple word overlap)"""
        words1 = set(text1.lower().split())
        words2 = set(text2.lower().split())

        if not words1 or not words2:
            return 0.0

        intersection = words1.intersection(words2)
        union = words1.union(words2)

        return len(intersection) / len(union) if union else 0.0

    def check_duplication(self, content: str, threshold: float = 0.7) -> tuple[bool, float]:
        """
        Check if content is too similar to previous content
        Returns: (is_duplicate, max_similarity)
        """
        if not self.previous_contents:
            return False, 0.0

        max_similarity = 0.0
        for prev_content in self.previous_contents:
            similarity = self.calculate_similarity(content, prev_content)
            max_similarity = max(max_similarity, similarity)

        return max_similarity >= threshold, max_similarity


class AIService:
    """AI generation service using Claude or OpenAI"""

    def __init__(self, provider: str = "anthropic"):
        self.provider = provider

        if provider == "anthropic":
            if not settings.ANTHROPIC_API_KEY:
                raise ValueError("ANTHROPIC_API_KEY not configured")
            self.client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
            self.model = "claude-3-5-sonnet-20241022"
        elif provider == "openai":
            if not settings.OPENAI_API_KEY:
                raise ValueError("OPENAI_API_KEY not configured")
            openai.api_key = settings.OPENAI_API_KEY
            self.model = "gpt-4"

    def _build_prompt(
        self,
        task: str,
        context: Dict[str, Any],
        custom_prompt: Optional[str] = None
    ) -> str:
        """Build prompt for AI generation"""
        base_prompts = {
            "reply": """Generate {count} reply candidates for the following social media post.

Context:
- Platform: {platform}
- Original post: {original_post}
- Tone: {tone}
- Max length: {max_length} characters

Requirements:
- Be engaging and authentic
- Follow the specified tone
- Avoid promotional language
- Do not use prohibited words
- Each reply should be unique

{custom_prompt}

Return response as JSON:
{{
  "drafts": [
    {{"text": "reply text", "reasoning": "why this reply works"}},
    ...
  ]
}}
""",
            "post": """Generate {count} social media post ideas.

Context:
- Platform: {platform}
- Topic: {topic}
- Target audience: {audience}
- Tone: {tone}
- Max length: {max_length} characters

Requirements:
- Be engaging and valuable
- Include relevant hashtags if appropriate
- Follow platform best practices
- Avoid promotional language
- Each post should be unique

{custom_prompt}

Return response as JSON:
{{
  "drafts": [
    {{"text": "post text", "hashtags": ["tag1", "tag2"], "reasoning": "why this works"}},
    ...
  ]
}}
""",
            "hashtags": """Generate relevant hashtags for the following content.

Content: {content}
Platform: {platform}
Target count: {count}

Requirements:
- Mix of popular and niche hashtags
- Relevant to content and platform
- Follow platform hashtag conventions

{custom_prompt}

Return response as JSON:
{{
  "hashtags": ["tag1", "tag2", ...],
  "reasoning": "explanation"
}}
""",
        }

        prompt_template = base_prompts.get(task, "")
        context["custom_prompt"] = custom_prompt or ""

        return prompt_template.format(**context)

    async def generate(
        self,
        task: str,
        context: Dict[str, Any],
        custom_prompt: Optional[str] = None,
        safety_filter: Optional[SafetyFilter] = None,
        duplication_checker: Optional[DuplicationChecker] = None
    ) -> Dict[str, Any]:
        """
        Generate content using AI
        Returns: {success, data, toxicity_score, duplication_rate, violations}
        """
        prompt = self._build_prompt(task, context, custom_prompt)

        try:
            # Generate content
            if self.provider == "anthropic":
                response = self.client.messages.create(
                    model=self.model,
                    max_tokens=2000,
                    messages=[
                        {"role": "user", "content": prompt}
                    ]
                )
                content_text = response.content[0].text
            else:
                response = openai.ChatCompletion.create(
                    model=self.model,
                    messages=[
                        {"role": "user", "content": prompt}
                    ]
                )
                content_text = response.choices[0].message.content

            # Parse JSON response
            try:
                generated_data = json.loads(content_text)
            except json.JSONDecodeError:
                # Try to extract JSON from markdown code blocks
                json_match = re.search(r'```json\n(.*?)\n```', content_text, re.DOTALL)
                if json_match:
                    generated_data = json.loads(json_match.group(1))
                else:
                    return {
                        "success": False,
                        "error": "Failed to parse AI response as JSON",
                        "raw_response": content_text
                    }

            # Safety checks
            violations = []
            max_duplication = 0.0

            if "drafts" in generated_data:
                for draft in generated_data["drafts"]:
                    text = draft.get("text", "")

                    # Safety filter
                    if safety_filter:
                        is_safe, draft_violations = safety_filter.check_content(text)
                        if not is_safe:
                            violations.extend(draft_violations)

                    # Duplication check
                    if duplication_checker:
                        is_duplicate, similarity = duplication_checker.check_duplication(text)
                        max_duplication = max(max_duplication, similarity)
                        if is_duplicate:
                            violations.append(f"High duplication detected: {similarity:.2%}")

            return {
                "success": True,
                "data": generated_data,
                "toxicity_score": 0.0,  # Would integrate with moderation API
                "duplication_rate": max_duplication,
                "violations": violations,
                "requires_approval": len(violations) > 0 or task == "reply"
            }

        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }

    async def generate_reply_candidates(
        self,
        platform: str,
        original_post: str,
        count: int = 3,
        tone: str = "professional",
        custom_prompt: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """Generate reply candidates"""
        context = {
            "platform": platform,
            "original_post": original_post,
            "count": count,
            "tone": tone,
            "max_length": kwargs.get("max_length", 280)
        }

        return await self.generate(
            "reply",
            context,
            custom_prompt,
            kwargs.get("safety_filter"),
            kwargs.get("duplication_checker")
        )

    async def generate_post_ideas(
        self,
        platform: str,
        topic: str,
        count: int = 3,
        tone: str = "professional",
        audience: str = "general",
        custom_prompt: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """Generate post ideas"""
        context = {
            "platform": platform,
            "topic": topic,
            "count": count,
            "tone": tone,
            "audience": audience,
            "max_length": kwargs.get("max_length", 280)
        }

        return await self.generate(
            "post",
            context,
            custom_prompt,
            kwargs.get("safety_filter"),
            kwargs.get("duplication_checker")
        )

    async def generate_hashtags(
        self,
        platform: str,
        content: str,
        count: int = 5,
        custom_prompt: Optional[str] = None
    ) -> Dict[str, Any]:
        """Generate hashtags"""
        context = {
            "platform": platform,
            "content": content,
            "count": count
        }

        return await self.generate("hashtags", context, custom_prompt)
