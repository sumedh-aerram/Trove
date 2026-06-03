-- Remove hand-written demo artifacts from packages/db/seed.sql (pre-2026).
-- Safe to re-run. Does not delete crawled HN/GitHub/arXiv rows.

delete from stars
where artifact_id in (
  select id from artifacts where canonical_url in (
    'https://github.com/lecture-genius/ai-lecture-summarizer',
    'https://github.com/paperpal/rag-chrome-extension',
    'https://github.com/clipnotes/whisper-video-summarizer',
    'https://github.com/mcphub/repo-search-mcp',
    'https://github.com/awesome-cursor/cursor-rules',
    'https://github.com/anthropic-community/claude-code-skills',
    'https://github.com/supastart/supabase-ai-saas',
    'https://github.com/hack-health/posture-coach',
    'https://github.com/recall-dev/flashcard-forge',
    'https://github.com/arxiv-tldr/paper-digest',
    'https://github.com/reviewbot/agentic-code-review',
    'https://github.com/fullstack-ai/nextjs-fastapi-multimodal'
  )
);

delete from user_posts
where artifact_id in (
  select id from artifacts where canonical_url in (
    'https://github.com/lecture-genius/ai-lecture-summarizer',
    'https://github.com/paperpal/rag-chrome-extension',
    'https://github.com/clipnotes/whisper-video-summarizer',
    'https://github.com/mcphub/repo-search-mcp',
    'https://github.com/awesome-cursor/cursor-rules',
    'https://github.com/anthropic-community/claude-code-skills',
    'https://github.com/supastart/supabase-ai-saas',
    'https://github.com/hack-health/posture-coach',
    'https://github.com/recall-dev/flashcard-forge',
    'https://github.com/arxiv-tldr/paper-digest',
    'https://github.com/reviewbot/agentic-code-review',
    'https://github.com/fullstack-ai/nextjs-fastapi-multimodal'
  )
);

delete from artifact_sources
where artifact_id in (
  select id from artifacts where canonical_url in (
    'https://github.com/lecture-genius/ai-lecture-summarizer',
    'https://github.com/paperpal/rag-chrome-extension',
    'https://github.com/clipnotes/whisper-video-summarizer',
    'https://github.com/mcphub/repo-search-mcp',
    'https://github.com/awesome-cursor/cursor-rules',
    'https://github.com/anthropic-community/claude-code-skills',
    'https://github.com/supastart/supabase-ai-saas',
    'https://github.com/hack-health/posture-coach',
    'https://github.com/recall-dev/flashcard-forge',
    'https://github.com/arxiv-tldr/paper-digest',
    'https://github.com/reviewbot/agentic-code-review',
    'https://github.com/fullstack-ai/nextjs-fastapi-multimodal'
  )
);

delete from artifacts where canonical_url in (
  'https://github.com/lecture-genius/ai-lecture-summarizer',
  'https://github.com/paperpal/rag-chrome-extension',
  'https://github.com/clipnotes/whisper-video-summarizer',
  'https://github.com/mcphub/repo-search-mcp',
  'https://github.com/awesome-cursor/cursor-rules',
  'https://github.com/anthropic-community/claude-code-skills',
  'https://github.com/supastart/supabase-ai-saas',
  'https://github.com/hack-health/posture-coach',
  'https://github.com/recall-dev/flashcard-forge',
  'https://github.com/arxiv-tldr/paper-digest',
  'https://github.com/reviewbot/agentic-code-review',
  'https://github.com/fullstack-ai/nextjs-fastapi-multimodal'
);
