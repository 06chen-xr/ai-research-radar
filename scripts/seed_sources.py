import json
from pathlib import Path

from source_policy import APPROVED_SOURCE_IDS, LANGUAGE_OVERRIDES, SOURCE_QUALITY

# Fields: id, name, url, category, source_type, topics, language, description, tier, feed_url
rows = [
# AI thinkers and independent researchers
("lilian-weng", "Lilian Weng / Lil'Log", "https://lilianweng.github.io", "ai-researcher", "personal-blog", ["agents", "reinforcement-learning", "research-surveys"], "en", "Deep technical explainers and research surveys.", "", "https://lilianweng.github.io/index.xml"),
("jason-wei", "Jason Wei", "https://www.jasonwei.net", "ai-researcher", "personal-site", ["reasoning", "prompt-engineering", "scaling"], "en", "Research notes on reasoning, prompting, and model behavior.", "", ""),
("andrej-karpathy", "Andrej Karpathy", "https://karpathy.github.io", "ai-researcher", "personal-blog", ["deep-learning", "ai-engineering", "education"], "en", "Code-driven explanations and reflections on AI and software.", "", ""),
("jay-alammar", "Jay Alammar", "https://jalammar.github.io", "ai-researcher", "personal-blog", ["visualization", "llms", "transformers"], "en", "Visual guides to transformers and modern language models.", "", ""),
("neel-nanda", "Neel Nanda", "https://www.neelnanda.io", "ai-researcher", "personal-site", ["interpretability", "agents", "research-methods"], "en", "Mechanistic interpretability research and hands-on resources.", "", ""),
("nelson-elhage", "Nelson Elhage", "https://blog.nelhage.com", "ai-researcher", "personal-blog", ["systems", "performance", "interpretability"], "en", "Deep dives into systems engineering and AI research.", "", ""),
("chip-huyen", "Chip Huyen", "https://huyenchip.com", "ai-engineering", "personal-blog", ["ml-systems", "agents", "evaluation"], "en", "Practical machine-learning systems and production AI.", "", ""),
("eugene-yan", "Eugene Yan", "https://eugeneyan.com", "ai-engineering", "personal-blog", ["llm-applications", "evaluation", "recommendation"], "en", "Applied ML, LLM systems, evaluation, and engineering patterns.", "", ""),
("tim-dettmers", "Tim Dettmers", "https://timdettmers.com", "ai-researcher", "personal-blog", ["model-efficiency", "hardware", "training"], "en", "Model efficiency, quantization, hardware, and training.", "", ""),
("francois-chollet", "François Chollet", "https://fchollet.substack.com", "ai-researcher", "newsletter", ["reasoning", "evaluation", "ai-opinions"], "en", "Critical perspectives on intelligence, reasoning, and evaluation.", "", ""),
("simon-willison", "Simon Willison", "https://simonwillison.net", "ai-engineering", "personal-blog", ["llm-tools", "prompt-engineering", "ai-coding"], "en", "Frequent hands-on notes on LLMs, tools, and coding workflows.", "", "https://simonwillison.net/atom/everything/"),
("hamel-husain", "Hamel Husain", "https://hamel.dev", "ai-engineering", "personal-site", ["evaluation", "llm-applications", "research-workflows"], "en", "Practical LLM evaluation and application engineering.", "", ""),
("swyx", "swyx / Latent Space", "https://www.swyx.io", "ai-engineering", "personal-blog", ["agents", "ai-engineering", "developer-tools"], "en", "AI engineering, developer workflows, and emerging practices.", "", ""),
("jan-leike", "Jan Leike / Alignment", "https://aligned.substack.com", "ai-researcher", "newsletter", ["alignment", "research-opinions", "safety"], "en", "Researcher perspectives on alignment and AI safety.", "", ""),
("alignment-forum", "Alignment Forum", "https://www.alignmentforum.org", "ai-community", "community", ["alignment", "research-discussion", "safety"], "en", "Long-form research discussion and AI safety essays.", "", ""),
("dwarkesh", "Dwarkesh Podcast", "https://www.dwarkesh.com", "interviews", "podcast", ["researcher-interviews", "ai-strategy", "technology"], "en", "Long-form interviews with AI researchers and technology leaders.", "", ""),
("latent-space", "Latent Space", "https://www.latent.space", "interviews", "podcast", ["ai-engineering", "agents", "researcher-interviews"], "en", "AI engineering interviews, tools, and practical workflows.", "", ""),
("cognitive-revolution", "The Cognitive Revolution", "https://www.cognitiverevolution.ai", "interviews", "podcast", ["ai-research", "researcher-interviews", "ai-strategy"], "en", "Long-form conversations about AI research and applications.", "", ""),
("pragmatic-engineer", "The Pragmatic Engineer", "https://newsletter.pragmaticengineer.com", "ai-engineering", "newsletter", ["software-engineering", "ai-coding", "engineering-culture"], "en", "Engineering practice, tools, and technology industry analysis.", "", ""),
# Independent research, evaluation, and thoughtful AI commentary
("gwern", "Gwern Branwen", "https://gwern.net/", "ai-researcher", "personal-blog", ["ai-essays", "scaling", "research-methods"], "en", "Long-form essays with extensive sourcing; AI-related posts only are indexed.", "", ""),
("import-ai", "Import AI / Jack Clark", "https://importai.substack.com/", "ai-researcher", "newsletter", ["ai-research", "industry-analysis", "policy"], "en", "Research-oriented analysis of important AI developments and their implications.", "", ""),
("interconnects", "Interconnects / Nathan Lambert", "https://www.interconnects.ai/", "ai-researcher", "newsletter", ["open-models", "post-training", "ai-research"], "en", "Researcher commentary on open models, post-training, and frontier AI.", "", ""),
("one-useful-thing", "One Useful Thing / Ethan Mollick", "https://www.oneusefulthing.org/", "ai-engineering", "newsletter", ["ai-practice", "workflow", "ai-capabilities"], "en", "Thoughtful practical writing about how AI changes work and problem-solving.", "", ""),
("ai-snake-oil", "AI Snake Oil", "https://www.aisnakeoil.com/", "ai-researcher", "newsletter", ["critical-analysis", "ai-evaluation", "ai-policy"], "en", "Evidence-focused critique of AI claims, evaluations, and real-world effects.", "", ""),
("epoch-ai", "Epoch AI", "https://epoch.ai/blog", "ai-academic", "research-blog", ["ai-trends", "compute", "scaling"], "en", "Quantitative research on AI progress, compute, and scaling trends.", "", ""),
("metr", "METR", "https://metr.org/blog/", "ai-academic", "research-blog", ["ai-evaluation", "agent-capabilities", "safety"], "en", "Empirical evaluations of frontier model capabilities and autonomous task performance.", "", ""),
("apollo-research", "Apollo Research", "https://www.apolloresearch.ai/blog", "ai-academic", "research-blog", ["alignment", "evaluations", "agent-behavior"], "en", "Technical research on model behavior, evaluations, and alignment.", "", ""),
("ai2", "AI2 / Allen Institute for AI", "https://allenai.org/blog", "ai-academic", "research-blog", ["open-research", "language-models", "datasets"], "en", "Research and open tools from the Allen Institute for AI.", "", ""),

# AI labs and engineering teams
("openai-blog", "OpenAI Research", "https://openai.com/research/", "ai-company", "research-blog", ["research", "reasoning", "agents", "safety"], "en", "Research posts and technical essays from OpenAI; generic product announcements are filtered.", "", ""),
("openai-developer", "OpenAI Developer Blog", "https://developers.openai.com/blog", "ai-engineering", "official-blog", ["api", "agents", "coding", "developer-tools"], "en", "Developer-focused guides, APIs, and agent workflows.", "", ""),
("anthropic-blog", "Anthropic Research", "https://www.anthropic.com/research", "ai-company", "research-blog", ["research", "safety", "alignment"], "en", "Research and analysis from Anthropic; generic corporate news is not the target.", "", ""),
("anthropic-engineering", "Anthropic Engineering", "https://www.anthropic.com/engineering", "ai-engineering", "official-blog", ["agents", "context-engineering", "evaluation"], "en", "Engineering articles on Claude, agents, and production AI.", "", ""),
("deepmind-blog", "Google DeepMind Blog", "https://deepmind.google/discover/blog", "ai-company", "official-blog", ["research", "reinforcement-learning", "multimodal"], "en", "Research breakthroughs and technical explanations.", "", ""),
("google-research", "Google Research Blog", "https://research.google/blog", "ai-company", "official-blog", ["research", "models", "systems"], "en", "Research papers, systems, and applied ML.", "", ""),
("meta-ai", "Meta AI Blog", "https://ai.meta.com/blog", "ai-company", "official-blog", ["open-models", "multimodal", "research"], "en", "Open models, research, and applied AI.", "", ""),
("mistral", "Mistral AI News", "https://mistral.ai/news", "ai-company", "official-blog", ["models", "open-models", "efficiency"], "en", "Model releases and technical updates.", "", ""),
("cohere", "Cohere Blog", "https://cohere.com/blog", "ai-company", "official-blog", ["enterprise-ai", "rag", "llm-applications"], "en", "Enterprise LLM applications and retrieval.", "", ""),
("huggingface", "Hugging Face Blog", "https://huggingface.co/blog", "ai-company", "official-blog", ["open-source", "models", "tools"], "en", "Open-source models, datasets, and practical guides.", "", ""),
("scale-ai", "Scale AI Blog", "https://scale.com/blog", "ai-company", "official-blog", ["data", "evaluation", "rlhf"], "en", "Data, evaluation, and model development.", "", ""),
("together-ai", "Together AI Blog", "https://www.together.ai/blog", "ai-company", "official-blog", ["open-models", "inference", "training"], "en", "Open model training and inference infrastructure.", "", ""),
("qwen", "Qwen Blog", "https://qwenlm.github.io/blog", "ai-company", "official-blog", ["open-models", "multimodal", "long-context"], "en", "Qwen model releases and technical reports.", "", ""),
("deepseek", "DeepSeek", "https://www.deepseek.com", "ai-company", "official-site", ["reasoning", "open-models", "training"], "zh", "Official DeepSeek model and research updates.", "", ""),
("moonshot", "Moonshot AI Blog", "https://www.moonshot.cn/blog", "ai-company", "official-blog", ["long-context", "reasoning", "models"], "zh", "Kimi and Moonshot AI product and research updates.", "", ""),
("minimax", "MiniMax Blog", "https://www.minimaxi.com/blog", "ai-company", "official-blog", ["multimodal", "speech", "models"], "zh", "MiniMax model and multimodal AI updates.", "", ""),
("zhipu", "Zhipu AI", "https://zhipuai.cn", "ai-company", "official-site", ["models", "agents", "chinese-llms"], "zh", "GLM models and product updates.", "", ""),
# Academic / community sources
("bair", "Berkeley AI Research (BAIR)", "https://bair.berkeley.edu/blog", "ai-academic", "research-blog", ["reinforcement-learning", "robotics", "research"], "en", "Research blog from Berkeley AI researchers.", "", ""),
("stanford-hai", "Stanford HAI", "https://hai.stanford.edu/news", "ai-academic", "research-blog", ["human-centered-ai", "policy", "research"], "en", "AI research, society, and policy.", "", ""),
("mit-csail", "MIT CSAIL", "https://www.csail.mit.edu/news", "ai-academic", "research-blog", ["systems", "ml", "robotics"], "en", "Computer science and AI research updates.", "", ""),
("cmu-ml", "CMU Machine Learning Blog", "https://blog.ml.cmu.edu", "ai-academic", "research-blog", ["ml-theory", "optimization", "deep-learning"], "en", "Machine learning research from Carnegie Mellon.", "", ""),
("mila", "Mila Blog", "https://mila.quebec/en/blog", "ai-academic", "research-blog", ["deep-learning", "causal-ai", "research"], "en", "Research from Mila and its collaborators.", "", ""),
("distill", "Distill", "https://distill.pub", "ai-academic", "research-publication", ["visualization", "deep-learning", "interpretability"], "en", "Interactive explanations of machine learning.", "", ""),
("shlab", "Shanghai AI Laboratory", "https://www.shlab.org.cn/news", "ai-academic", "research-blog", ["open-source", "multimodal", "research"], "zh", "Chinese AI research and open-source projects.", "", ""),
# Quantitative trading firms and systematic managers
("jane-street", "Jane Street", "https://blog.janestreet.com/archive/", "quant-firm", "official-blog", ["feature-engineering", "market-microstructure", "ml-systems", "research-engineering"], "en", "Technical articles from Jane Street; includes ML and engineering topics.", "Tier 1", ""),
("xtx-markets", "XTX Markets", "https://www.xtxmarkets.com/tech/", "quant-firm", "official-blog", ["ml-systems", "data-infrastructure", "quant-research"], "en", "Public technology articles and research infrastructure write-ups.", "Tier 1", ""),
("citadel-securities", "Citadel Securities", "https://www.citadelsecurities.com/news-and-insights/", "quant-firm", "official-blog", ["market-structure", "execution", "technology"], "en", "Market structure, technology, and public research insights.", "Tier 1", ""),
("citadel", "Citadel", "https://www.citadel.com/insights/", "quant-firm", "official-blog", ["systematic-investing", "research", "markets"], "en", "Public investment and market insights.", "Tier 1", ""),
("hrt", "Hudson River Trading", "https://www.hudsonrivertrading.com", "quant-firm", "official-site", ["market-microstructure", "trading-systems", "research-engineering"], "en", "Company site; track public technical content and talks.", "Tier 1", ""),
("jump-trading", "Jump Trading", "https://www.jumptrading.com", "quant-firm", "official-site", ["trading-systems", "market-microstructure", "research"], "en", "Company site; track public talks and technical content.", "Tier 1", ""),
("two-sigma", "Two Sigma", "https://www.twosigma.com/insights/", "quant-firm", "official-blog", ["data-science", "machine-learning", "systematic-investing"], "en", "Research, data science, and systematic investment insights.", "Tier 1", ""),
("deshaw", "D. E. Shaw", "https://www.deshaw.com", "quant-firm", "official-site", ["quant-research", "technology", "research"], "en", "Company site; track public technical and research publications.", "Tier 1", ""),
("optiver", "Optiver", "https://optiver.com/insights/", "quant-firm", "official-blog", ["market-microstructure", "trading-systems", "execution"], "en", "Trading technology, market structure, and engineering.", "Tier 2", ""),
("imc", "IMC Trading", "https://www.imc.com/us/blogs", "quant-firm", "official-blog", ["trading-technology", "machine-learning", "research"], "en", "Technology and research content from IMC.", "Tier 2", ""),
("sig", "Susquehanna International Group (SIG)", "https://sig.com/insights/", "quant-firm", "official-blog", ["options", "market-structure", "trading"], "en", "Public market and trading insights.", "Tier 2", ""),
("drw", "DRW", "https://www.drw.com/insights", "quant-firm", "official-blog", ["trading", "technology", "markets"], "en", "Trading, technology, and market commentary.", "Tier 2", ""),
("tower", "Tower Research Capital", "https://www.tower-research.com", "quant-firm", "official-site", ["low-latency", "trading-systems", "quant-research"], "en", "Company site; track public engineering and recruiting talks.", "Tier 2", ""),
("man-group", "Man Group / AHL", "https://www.man.com/insights", "quant-firm", "official-blog", ["systematic-investing", "trend-following", "machine-learning"], "en", "Systematic investing, trend following, and research.", "Tier 2", ""),
("aqr", "AQR Capital Management", "https://www.aqr.com/Insights", "quant-firm", "research-publication", ["factor-investing", "portfolio-construction", "empirical-finance"], "en", "Research on factors, systematic investing, and portfolio construction.", "Tier 3", ""),
("pdt", "PDT Partners", "https://www.pdtpartners.com", "quant-firm", "official-site", ["quant-research", "systematic-investing", "research"], "en", "Public company materials and research-related content.", "Tier 3", ""),
("squarepoint", "Squarepoint Capital", "https://www.squarepoint-capital.com", "quant-firm", "official-site", ["quant-research", "systematic-investing", "technology"], "en", "Company site; monitor public research and technical talks.", "Tier 3", ""),
("qube", "Qube Research & Technologies", "https://www.qube-rt.com", "quant-firm", "official-site", ["quant-research", "machine-learning", "systematic-investing"], "en", "Company site; monitor public research and technical content.", "Tier 3", ""),
("point72", "Point72 / Cubist", "https://point72.com", "quant-firm", "official-site", ["systematic-investing", "data-science", "quant-research"], "en", "Company site; monitor public research and data-science material.", "Tier 3", ""),
("worldquant", "WorldQuant", "https://www.worldquant.com", "quant-firm", "official-site", ["alpha-research", "quant-research", "education"], "en", "Quantitative research and public educational resources.", "Tier 3", ""),
("voleon", "Voleon", "https://voleon.com", "quant-firm", "official-site", ["machine-learning", "systematic-investing", "quant-research"], "en", "Machine-learning-driven investment firm; monitor public materials.", "Tier 3", ""),
("virtu", "Virtu Financial", "https://www.virtu.com/insights/", "quant-firm", "official-blog", ["market-structure", "execution", "trading-technology"], "en", "Market structure, execution, and trading technology.", "Tier 4", ""),
("flow-traders", "Flow Traders", "https://www.flowtraders.com", "quant-firm", "official-site", ["market-making", "market-structure", "trading"], "en", "Market-making and market-structure public materials.", "Tier 4", ""),
("akuna", "Akuna Capital", "https://akunacapital.com/blog", "quant-firm", "official-blog", ["options", "trading-technology", "quant-research"], "en", "Options trading, technical content, and engineering.", "Tier 4", ""),
("wolverine", "Wolverine Trading", "https://www.wolve.com", "quant-firm", "official-site", ["options", "market-making", "trading"], "en", "Company site; track public technical material.", "Tier 4", ""),
("belvedere", "Belvedere Trading", "https://belvederetrading.com", "quant-firm", "official-site", ["options", "trading-technology", "market-making"], "en", "Company site; track public trading and technology content.", "Tier 4", ""),
("maven", "Maven Securities", "https://www.mavensecurities.com", "quant-firm", "official-site", ["market-making", "trading-technology", "quant-research"], "en", "Specialist trading firm; monitor public talks and technical material.", "Tier 5", ""),
("tibra", "Tibra", "https://tibra.com", "quant-firm", "official-site", ["quant-research", "systematic-trading", "technology"], "en", "Quantitative trading firm; monitor public research and interviews.", "Tier 5", ""),
("eclipse-trading", "Eclipse Trading", "https://www.eclipsetrading.com", "quant-firm", "official-site", ["options", "market-making", "trading-technology"], "en", "Asia-focused trading firm; monitor public talks and technology content.", "Tier 5", ""),
("geneva-trading", "Geneva Trading", "https://genevatrading.com", "quant-firm", "official-site", ["market-making", "trading-systems", "quant-research"], "en", "Trading firm; monitor public engineering and recruiting talks.", "Tier 5", ""),
("ctc-trading", "CTC Trading", "https://www.ctc.com", "quant-firm", "official-site", ["market-making", "trading-technology", "quant-research"], "en", "Trading firm; monitor public technical and industry content.", "Tier 5", ""),
("peak6", "PEAK6", "https://peak6.com", "quant-firm", "official-site", ["trading", "technology", "markets"], "en", "Trading and technology company; monitor public interviews and talks.", "Tier 5", ""),
# Interviews and trading research media
("top-traders-unplugged", "Top Traders Unplugged", "https://www.toptradersunplugged.com", "interviews", "podcast", ["systematic-investing", "trend-following", "manager-interviews"], "en", "Interviews and discussions on systematic trading and investing.", "", ""),
("chat-with-traders", "Chat With Traders", "https://chatwithtraders.com", "interviews", "podcast", ["trader-interviews", "trading-systems", "risk"], "en", "Interviews with traders and systematic market participants.", "", ""),
("alpha-exchange", "The Alpha Exchange", "https://www.alphaexchange.com", "interviews", "podcast", ["quant-research", "market-structure", "researcher-interviews"], "en", "Conversations with quantitative and financial researchers.", "", ""),
("flirting-with-models", "Flirting With Models", "https://flirtingwithmodels.com", "interviews", "podcast", ["quant-research", "factor-investing", "researcher-interviews"], "en", "Quantitative finance interviews and research discussions.", "", ""),
]

index_source_ids = {
    "lilian-weng", "jason-wei", "andrej-karpathy", "chris-olah", "jay-alammar",
    "neel-nanda", "nelson-elhage", "tim-dettmers",
    "chip-huyen", "eugene-yan", "jan-leike", "alignment-forum",
    "openai-blog", "anthropic-blog", "deepmind-blog", "meta-ai", "mistral", "cohere",
    "huggingface", "scale-ai", "together-ai", "qwen", "moonshot", "bytedance-ailab",
    "minimax", "zhipu", "bair", "stanford-hai", "mit-csail", "cmu-ml", "mila",
    "distill", "shlab"
}

sources = []
for row in rows:
    sid, name, url, category, source_type, topics, language, description, tier, feed_url = row
    item = {
        "id": sid,
        "name": name,
        "url": url,
        "category": category,
        "source_type": source_type,
        "topics": topics,
        "language": LANGUAGE_OVERRIDES.get(sid, language),
        "description": description,
        "tier": tier or None,
        "enabled": sid in APPROVED_SOURCE_IDS,
        "review_status": "approved" if sid in APPROVED_SOURCE_IDS else ("language-filtered" if language != "en" else "not-curated"),
        "source_quality": SOURCE_QUALITY.get(sid, "watchlist"),
        "feed_url": feed_url or None,
        "source_index": "joeseesun/ai-blog-res" if sid in index_source_ids else ("curated-quant-and-interviews" if category in ("quant-firm", "interviews") else "curated-ai-sources")
    }
    sources.append(item)

out = Path(__file__).resolve().parents[1] / "data" / "sources.json"
out.write_text(json.dumps({
    "updated_at": None,
    "source_index": "https://github.com/joeseesun/ai-blog-res/blob/main/AI%E5%8D%9A%E5%AE%A2%E8%B5%84%E6%BA%90-%E5%AE%8C%E6%95%B4%E7%B4%A2%E5%BC%95.md",
    "note": "Curated English-first registry. Only approved sources are monitored; new upstream entries remain pending review.",
    "sources": sources
}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(f"Wrote {len(sources)} sources to {out}")
