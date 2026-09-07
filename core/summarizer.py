"""
Conversation summarization using headless Claude
"""
import json
import os
import subprocess
import tempfile
from datetime import datetime
from typing import Dict, Any, List, Optional

from core.models import ConversationSummary
from core.searcher import SessionSearcher


class ConversationSummarizer:
    """Handles intelligent summarization of daily conversations"""

    def __init__(self):
        self.searcher = SessionSearcher()

    def summarize_daily_conversations(self, date: str, style: str = "journal",
                                    project_filter: Optional[str] = None) -> Dict[str, Any]:
        """Main entry point for daily conversation summarization"""

        # Use the searcher to find conversations for the date
        # Search for any content (broad query) within the specific date range
        search_result = self.searcher.search_conversations(
            query="the",  # Common word to catch most conversations
            start_time=f"{date}T00:00:00",
            end_time=f"{date}T23:59:59",
            project_filter=project_filter,
            role_filter="user",  # Focus on user messages for summary
            days_back=30,  # Look back far enough to catch the specific date
            context_window=1
        )

        if search_result.get('total_matches', 0) == 0:
            return {
                'date': date,
                'total_sessions': 0,
                'total_messages': 0,
                'summary_style': style,
                'summary': 'No conversations found for this date.',
                'key_topics': [],
                'insights': [],
                'stories': [],
                'projects_mentioned': [],
                'people_mentioned': []
            }

        # Prepare content for Claude analysis
        conversation_content = self._prepare_summary_content(search_result, date)

        # Generate summary using headless Claude
        summary_result = self._call_headless_claude_summary(conversation_content, style, date)

        # Calculate session count
        unique_sessions = len(set(r['session_id'] for r in search_result['results']))

        return {
            'date': date,
            'total_sessions': unique_sessions,
            'total_messages': search_result['total_matches'],
            'summary_style': style,
            'summary': summary_result.get('summary', 'Summary generation failed'),
            'key_topics': summary_result.get('key_topics', []),
            'insights': summary_result.get('insights', []),
            'stories': summary_result.get('stories', []),
            'projects_mentioned': summary_result.get('projects_mentioned', []),
            'people_mentioned': summary_result.get('people_mentioned', []),
            'error': summary_result.get('error')
        }

    def _prepare_summary_content(self, search_result: Dict[str, Any], date: str) -> str:
        """Prepare conversation content for Claude analysis"""
        content_parts = []
        content_parts.append(f"# Daily Conversations Summary - {date}")
        content_parts.append(f"Total messages: {search_result['total_matches']}")
        content_parts.append("")

        for result in search_result['results']:
            content_parts.append(f"## Session: {result['session_id']} ({result['project']})")

            # Include the actual message content (not just context window)
            content_parts.append(f"**User Message:** {result['match_content'][:500]}...")
            content_parts.append("")

        # Limit total content to prevent timeout
        full_content = "\n".join(content_parts)
        if len(full_content) > 6000:
            full_content = full_content[:6000] + "\n\n[Content truncated to prevent timeout]"

        return full_content

    def _call_headless_claude_summary(self, conversation_content: str, style: str, date: str) -> Dict[str, Any]:
        """Call headless Claude to generate summary"""
        return self._call_headless_claude(conversation_content, style, date)

    def summarize_conversations(self, conversations_data: Dict[str, Any], style: str = "journal") -> ConversationSummary:
        """Generate intelligent summary using headless Claude"""

        if 'error' in conversations_data:
            return ConversationSummary(
                date=conversations_data.get('date', 'unknown'),
                total_sessions=0,
                total_messages=0,
                summary_style=style,
                summary_text="",
                key_topics=[],
                insights=[],
                stories=[],
                projects_mentioned=[],
                people_mentioned=[],
                error=conversations_data['error']
            )

        # Prepare conversation content for Claude
        conversation_content = self._prepare_conversation_content(conversations_data, style)

        # Generate summary using headless Claude
        summary_result = self._call_headless_claude(conversation_content, style, conversations_data['date'])

        if summary_result.get('error'):
            return ConversationSummary(
                date=conversations_data['date'],
                total_sessions=conversations_data['session_count'],
                total_messages=conversations_data['total_messages'],
                summary_style=style,
                summary_text="",
                key_topics=[],
                insights=[],
                stories=[],
                projects_mentioned=[],
                people_mentioned=[],
                error=summary_result['error']
            )

        # Parse Claude's response
        return self._parse_summary_response(
            summary_result['summary'],
            conversations_data,
            style
        )

    def _prepare_conversation_content(self, conversations_data: Dict[str, Any], style: str) -> str:
        """Prepare conversation content for Claude analysis"""

        content_parts = []
        content_parts.append(f"# Daily Conversations - {conversations_data['date']}")
        content_parts.append(f"Sessions: {conversations_data['session_count']}")
        content_parts.append(f"Total Messages: {conversations_data['total_messages']}")
        content_parts.append("")

        for conv in conversations_data['conversations']:
            content_parts.append(f"## Session: {conv['session_id']} ({conv['project']})")

            for msg in conv['messages']:
                timestamp = msg.timestamp.strftime('%H:%M') if msg.timestamp else 'unknown'
                content_parts.append(f"**{timestamp} - {msg.role}:** {msg.content[:500]}...")

            content_parts.append("")

        return "\n".join(content_parts)

    def _call_headless_claude(self, conversation_content: str, style: str, date: str) -> Dict[str, Any]:
        """Call headless Claude to generate summary"""

        # The rules every style shares. The reader of one of these summaries is
        # a software engineer resuming or searching past Claude Code work, so a
        # summary is only useful if it names the files, commands and errors
        # involved rather than describing the work in general terms.
        common_rules = (
            "Write plain sentences. Do not use marketing language and do not "
            "praise the work. Keep every identifier exactly as it appears in "
            "the transcript: file paths, function and class names, commands, "
            "flags, environment variables, error text, branch names and commit "
            "hashes. Do not invent anything, and do not guess at an outcome the "
            "transcript does not state; say that the transcript does not say. "
            "Leave a list empty rather than filling it with plausible entries."
        )

        # Style-specific prompts, written for software engineering sessions.
        prompts = {
            "journal": f"""Summarise the Claude Code sessions from {date} as a work log for the engineer who ran them.

Cover, in this order:
- What each session was asked to do, and whether it finished, stalled, or was abandoned.
- The files, functions, commands and identifiers that were touched.
- The errors and test failures that came up, and how each was resolved or why it was not.
- What was left open, and the next step it needs.

{common_rules}""",

            "insights": f"""Summarise the Claude Code sessions from {date} as the decisions and findings worth keeping.

Cover, in this order:
- Each decision taken, the reason given for it, and the alternative it rejected.
- Facts established by running something: measurements, timings, counts, versions, and the command that produced each.
- Behaviour of a library, tool or interface that was discovered by probing rather than read from its documentation.
- Mistakes made and what they cost, so that the same one is not repeated.

{common_rules}""",

            "stories": f"""Summarise the Claude Code sessions from {date} as the debugging episodes worth recalling.

For each episode, state:
- The symptom as it first appeared, including the exact error text or the wrong output.
- What was ruled out on the way, and how it was ruled out.
- The actual cause.
- The change that fixed it, named by file and by function.
- Whether a test or a check now covers it.

Report only episodes the transcript actually contains. {common_rules}"""
        }

        # Aliases, so that a caller can name the coding-oriented style directly
        # without knowing which of the original three keys carries it.
        style = {
            "worklog": "journal",
            "decisions": "insights",
            "debugging": "stories",
        }.get(style, style)

        prompt = prompts.get(style, prompts["journal"])

        # Create temporary file with conversation content
        try:
            with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as temp_file:
                temp_file.write(conversation_content)
                temp_file_path = temp_file.name

            # Call headless Claude
            claude_prompt = f"""{prompt}

Return only a JSON object, with no text before or after it, in exactly this format:
{{
    "summary": "The prose summary described above.",
    "key_topics": ["a short phrase naming a subject the sessions worked on"],
    "insights": ["one decision, measurement or discovered behaviour, with its reason"],
    "stories": ["one debugging episode: the symptom, the cause, and the fix"],
    "projects_mentioned": ["a repository, project or directory the work happened in"],
    "people_mentioned": ["a person named in the sessions; empty when none were"]
}}

Every list holds plain strings. Leave a list empty when the sessions give it
nothing to hold.

Session content to summarise:
{conversation_content[:5000]}...
"""

            # The model is whatever the `claude` command is configured to use,
            # unless CC_SESSION_SEARCH_MODEL names one. Pinning a model here
            # breaks the tool whenever that model identifier is retired, which
            # is what happened to the `claude-3-5-sonnet-latest` this replaced.
            command = ['claude', '--print', '--output-format', 'text']
            model = os.environ.get('CC_SESSION_SEARCH_MODEL', '').strip()
            if model:
                command += ['--model', model]
            command.append(claude_prompt)

            result = subprocess.run(
                command,
                capture_output=True,
                text=True
            )

            # Clean up temp file
            os.unlink(temp_file_path)

            if result.returncode == 0:
                return {'summary': result.stdout.strip()}
            else:
                return {'error': f'Claude headless failed: {result.stderr}'}

        except Exception as e:
            return {'error': f'Error calling headless Claude: {str(e)}'}

    def _parse_summary_response(self, claude_response: str, conversations_data: Dict[str, Any], style: str) -> ConversationSummary:
        """Parse Claude's response into structured summary"""

        # Try to extract JSON from response
        summary_data = self._extract_json_from_response(claude_response)

        if not summary_data:
            # Fallback: use raw response as summary
            return ConversationSummary(
                date=conversations_data['date'],
                total_sessions=conversations_data['session_count'],
                total_messages=conversations_data['total_messages'],
                summary_style=style,
                summary_text=claude_response,
                key_topics=[],
                insights=[],
                stories=[],
                projects_mentioned=[],
                people_mentioned=[]
            )

        return ConversationSummary(
            date=conversations_data['date'],
            total_sessions=conversations_data['session_count'],
            total_messages=conversations_data['total_messages'],
            summary_style=style,
            summary_text=summary_data.get('summary', ''),
            key_topics=summary_data.get('key_topics', []),
            insights=summary_data.get('insights', []),
            stories=summary_data.get('stories', []),
            projects_mentioned=summary_data.get('projects_mentioned', []),
            people_mentioned=summary_data.get('people_mentioned', [])
        )

    def _extract_json_from_response(self, response: str) -> Optional[Dict[str, Any]]:
        """Extract JSON data from Claude's response"""
        try:
            # Look for JSON block in response
            if '```json' in response:
                start = response.find('```json') + 7
                end = response.find('```', start)
                json_str = response[start:end].strip()
            elif '{' in response and '}' in response:
                start = response.find('{')
                end = response.rfind('}') + 1
                json_str = response[start:end]
            else:
                return None

            return json.loads(json_str)
        except (json.JSONDecodeError, ValueError):
            return None

    def summarize_time_range(self, start_time: str, end_time: str,
                           style: str = "journal", project_filter: Optional[str] = None) -> Dict[str, Any]:
        """Summarize conversations within a specific time range using search functionality"""

        # Use the searcher to find conversations in the time range
        search_result = self.searcher.search_conversations(
            query="the",  # Common word to catch most conversations
            start_time=start_time,
            end_time=end_time,
            project_filter=project_filter,
            role_filter="user",  # Focus on user messages for summary
            days_back=30,  # Look back far enough to catch the time range
            context_window=1
        )

        if search_result.get('total_matches', 0) == 0:
            return {
                'start_time': start_time,
                'end_time': end_time,
                'total_sessions': 0,
                'total_messages': 0,
                'summary_style': style,
                'summary': 'No conversations found for this time range.',
                'key_topics': [],
                'insights': [],
                'stories': [],
                'projects_mentioned': [],
                'people_mentioned': []
            }

        # Prepare content for Claude analysis
        conversation_content = self._prepare_time_range_content(search_result, start_time, end_time)

        # Generate summary using headless Claude
        summary_result = self._call_headless_claude_summary(conversation_content, style, f"{start_time} to {end_time}")

        # Calculate session count
        unique_sessions = len(set(r['session_id'] for r in search_result['results']))

        return {
            'start_time': start_time,
            'end_time': end_time,
            'total_sessions': unique_sessions,
            'total_messages': search_result['total_matches'],
            'summary_style': style,
            'summary': summary_result.get('summary', 'Summary generation failed'),
            'key_topics': summary_result.get('key_topics', []),
            'insights': summary_result.get('insights', []),
            'stories': summary_result.get('stories', []),
            'projects_mentioned': summary_result.get('projects_mentioned', []),
            'people_mentioned': summary_result.get('people_mentioned', []),
            'error': summary_result.get('error')
        }

    def _prepare_time_range_content(self, search_result: Dict[str, Any], start_time: str, end_time: str) -> str:
        """Prepare time range conversation content for Claude analysis"""
        content_parts = []
        content_parts.append(f"# Time Range Conversations Summary - {start_time} to {end_time}")
        content_parts.append(f"Total messages: {search_result['total_matches']}")
        content_parts.append("")

        for result in search_result['results']:
            content_parts.append(f"## Session: {result['session_id']} ({result['project']})")
            content_parts.append(f"**Time:** {result['match_timestamp']}")
            content_parts.append(f"**User Message:** {result['match_content'][:500]}...")
            content_parts.append("")

        # Limit total content to prevent timeout
        full_content = "\n".join(content_parts)
        if len(full_content) > 6000:
            full_content = full_content[:6000] + "\n\n[Content truncated to prevent timeout]"

        return full_content

