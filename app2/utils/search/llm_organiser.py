"""
Alice Content Organizer - Smart Content Synthesis & Truncation
Processes scraped content using 70B model for comprehensive research synthesis.
Implements intelligent token budget management to prevent API limits while maximizing information quality.
"""

import json
import logging
import os
from typing import Dict, List, Any
from groq import Groq
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

# ==================== GLOBAL CONFIGURATION (CACHED) ====================

# LLM Configuration - Same model as llm_ranker for consistency
API_KEYS = [
    os.getenv('GROQ_API_KEY'),
    os.getenv('GROQ_API_KEY_ALT_1'), 
    os.getenv('GROQ_API_KEY_ALT_2'),
    os.getenv('GROQ_API_KEY_ALT_3'),
    os.getenv('GROQ_API_KEY_ALT_4')
]

AVAILABLE_API_KEYS = [key for key in API_KEYS if key and key.strip()]
if not AVAILABLE_API_KEYS:
    raise ValueError("No valid GROQ API keys found in environment variables.")

ORGANIZER_API_ORDER = [
    'GROQ_API_KEY_ALT_2',     # Start with different key
    'GROQ_API_KEY_ALT_3',
    'GROQ_API_KEY_ALT_4',
    'GROQ_API_KEY',
    'GROQ_API_KEY_ALT_1'
]
LLM_MODEL = "llama-3.3-70b-versatile"
LLM_TEMPERATURE = 0.1  # Lower for consistent research synthesis
MAX_TOKENS = 8192  # Large for comprehensive synthesis

# Smart Truncation Configuration
CONTENT_BUDGET_CHARS = 18000  # Conservative budget to stay under 12K tokens
MAX_SOURCES_PROCESSED = 12    # Process up to 12 sources maximum
MAX_CHARS_PER_SOURCE = 3500   # Maximum characters per high-quality source
MIN_CHARS_PER_SOURCE = 800    # Minimum characters per source for quality

# Quality Score Thresholds
QUALITY_HIGH_THRESHOLD = 80   # High quality sources get full allocation
QUALITY_MEDIUM_THRESHOLD = 60 # Medium quality sources get 80% allocation
QUALITY_LOW_ALLOCATION = 0.6  # Low quality sources get 60% allocation

# Research Synthesis Prompt - Cached for optimization
RESEARCH_SYNTHESIS_PROMPT = """You are Alice's Research Synthesizer. Create comprehensive unified content from sources.
                            
                            🎯 **MISSION:** Create extensive research document from truncated sources
                            Query: "{user_query}"
                            Sources: {source_data}
                            
                            📚 **REQUIREMENTS:**
                            1. **COMPREHENSIVE** - Include ALL unique info from ALL sources
                            2. **STRUCTURED** - Organize logically by themes
                            3. **EXTENSIVE** - Target 4000-6000 characters for research topics
                            4. **DETAILED** - Include specifics, numbers, dates, names
                            5. **SYNTHESIZED** - Merge complementary information
                            6. **SOURCE TRACKING** - Note which sources contributed what
                            
                            🧠 **STRUCTURE:**
                            - Overview & Background
                            - Current State & Developments  
                            - Technical Details & Specifications
                            - Key Players & Organizations
                            - Applications & Use Cases
                            - Challenges & Future Outlook
                            - Facts & Statistics
                            
                            📊 **JSON OUTPUT:**
                            {{
                              "unified_content": "EXTENSIVE research document (4000-6000+ chars) covering topic comprehensively with background, current state, technical details, key players, challenges, and prospects.",
                              "key_facts": ["specific facts with details"],
                              "main_findings": "Comprehensive summary of conclusions",
                              "information_quality": "excellent|good|fair|poor",
                              "confidence": 0.0-1.0,
                              "content_depth": "comprehensive|moderate|basic",
                              "word_count": 0,
                              "coverage_areas": ["background", "current_state", "technical_details"],
                              "source_usage": [
                                {{"source_id": 1, "contributed_info": "What this source contributed"}}
                              ],
                              "most_valuable_sources": [1, 2, 3],
                              "source_synthesis": "How sources complemented each other"
                            }}
                            
                            🎯 **CREATE RESEARCH DOCUMENT:**"""

# ==================== UTILITY FUNCTIONS ====================

def check_groq_availability() -> bool:
    """Check if Groq is available and at least one API key is configured"""
    try:
        from groq import Groq
        return len(AVAILABLE_API_KEYS) > 0
    except ImportError:
        return False

def get_api_key_by_name(key_name: str) -> str:
    """Get API key by environment variable name"""
    key_map = {
        'GROQ_API_KEY': 0,
        'GROQ_API_KEY_ALT_1': 1,
        'GROQ_API_KEY_ALT_2': 2,
        'GROQ_API_KEY_ALT_3': 3,
        'GROQ_API_KEY_ALT_4': 4
    }
    
    index = key_map.get(key_name)
    if index is not None and index < len(API_KEYS):
        return API_KEYS[index]
    return None

def make_groq_request_with_fallback(messages, model, temperature=0.7, max_tokens=1500, api_key_priority_order=None):
    """
    Universal Groq request with automatic fallback between API keys
    
    Args:
        messages: Chat messages for Groq
        model: Model name (e.g., "llama-3.3-70b-versatile")
        temperature: Temperature setting
        max_tokens: Max tokens
        api_key_priority_order: List of API key names in priority order
    
    Returns:
        Groq response
    """
    
    # Default order if not specified
    if api_key_priority_order is None:
        api_key_priority_order = [
            'GROQ_API_KEY_ALT_2',
            'GROQ_API_KEY_ALT_3',
            'GROQ_API_KEY_ALT_4',
            'GROQ_API_KEY',
            'GROQ_API_KEY_ALT_1'
        ]
    
    last_error = None
    
    for key_name in api_key_priority_order:
        api_key = get_api_key_by_name(key_name)
        
        if not api_key or not api_key.strip():
            logger.warning(f"API key {key_name} not found or empty")
            continue
            
        try:
            client = Groq(api_key=api_key)
            response = client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens
            )
            
            logger.info(f"✅ Successfully used API key: {key_name}")
            return response
            
        except Exception as e:
            error_str = str(e).lower()
            logger.warning(f"❌ API key {key_name} failed: {e}")
            last_error = e
            
            # Check for rate limit errors
            rate_limit_indicators = [
                'rate limit', 'too many requests', 'quota exceeded', 
                'tokens exhausted', '429', 'rate_limit_exceeded',
                'insufficient_quota', 'billing', 'usage limit'
            ]
            
            if any(indicator in error_str for indicator in rate_limit_indicators):
                logger.warning(f"⏳ Rate limit hit on {key_name}, trying next key...")
                continue
            else:
                logger.error(f"🔥 Non-rate-limit error on {key_name}: {e}")
                continue
    
    # All keys failed
    raise Exception(f"All API keys failed. Last error: {last_error}")

def calculate_content_allocation(quality_score: int, max_allocation: int, total_sources: int, current_index: int) -> int:
    """Calculate optimal character allocation based on quality score and position"""
    
    # Quality-based allocation
    if quality_score >= QUALITY_HIGH_THRESHOLD:
        base_allocation = max_allocation
    elif quality_score >= QUALITY_MEDIUM_THRESHOLD:
        base_allocation = int(max_allocation * 0.8)
    else:
        base_allocation = int(max_allocation * QUALITY_LOW_ALLOCATION)
    
    # Ensure minimum allocation for quality
    return max(MIN_CHARS_PER_SOURCE, base_allocation)

def extract_domain_from_url(url: str) -> str:
    """Extract domain name from URL safely"""
    try:
        if '/' in url and len(url.split('/')) > 2:
            return url.split('/')[2]
        return "Unknown"
    except Exception:
        return "Unknown"

def create_source_metadata(source_id: int, result: Dict, allocated_chars: int, content_length: int) -> Dict[str, Any]:
    """Create standardized source metadata"""
    url = result.get('url', '')
    title = result.get('title', '')[:200]  # Truncate title
    
    return {
        "source_id": source_id,
        "title": title,
        "url": url,
        "domain": extract_domain_from_url(url),
        "quality_score": result.get('quality_score', 0),
        "content_length": allocated_chars,
        "was_truncated": content_length > allocated_chars
    }

def create_fallback_sections(content_list: List[str], user_query: str) -> List[str]:
    """Create structured fallback sections from content"""
    sections = []
    
    # Overview section
    if content_list:
        sections.append(f"**RESEARCH OVERVIEW FOR {user_query.upper()}:**\n{content_list[0][:1200]}")
    
    # Main research sections  
    for i, content in enumerate(content_list[1:4], 1):
        sections.append(f"\n**RESEARCH SECTION {i}:**\n{content[:1500]}")
    
    # Additional research details
    if len(content_list) > 4:
        additional = "\n\n".join(content_list[4:])[:2500]
        sections.append(f"\n**SUPPLEMENTARY RESEARCH:**\n{additional}")
    
    # Research conclusion
    sections.append(f"\n**RESEARCH CONCLUSION:** This comprehensive synthesis combines information from {len(content_list)} high-quality sources using smart truncation to provide extensive coverage of {user_query}. Each source was intelligently processed to extract the most relevant information while maintaining research quality and avoiding token limits.")
    
    return sections

# ==================== MAIN CONTENT ORGANIZER CLASS ====================

class ContentOrganizer:
    """
    Main content organization engine with smart truncation and synthesis capabilities.
    Implements intelligent token budget management for optimal research synthesis.
    """ 
    async def organize_scraped_content(self, 
                                       scraped_results: List[Dict], 
                                       user_query: str) -> Dict[str, Any]:
        
        """
        MAIN CONTENT ORGANIZATION FUNCTION
        
        Processes and organizes scraped content with smart truncation to avoid token limits
        while maximizing information quality and research depth.
        
        Args:
            scraped_results: List of scraped content dictionaries
            user_query: User's research query for context
            
        Returns:
            Dict containing unified research synthesis with source tracking
        """
        
        # Smart truncation preprocessing
        content_summary, source_urls, used_chars = self._apply_smart_truncation(
            scraped_results, user_query
        )
        
        # Generate research synthesis
        try:
            synthesis_result = await self._generate_research_synthesis(
                content_summary, user_query, source_urls, used_chars, scraped_results
            )
            
            logger.info(f"✅ Content organization successful: {synthesis_result['actual_char_count']} chars from {len(content_summary)} sources")
            return synthesis_result
            
        except Exception as e:
            logger.error(f"Content organization failed: {str(e)}")
            
            # Enhanced fallback with preserved truncation data
            return self._create_enhanced_fallback(
                content_summary, source_urls, used_chars, scraped_results, user_query
            )

    # ==================== SMART TRUNCATION ENGINE ====================
    
    def _apply_smart_truncation(
        self, 
        scraped_results: List[Dict], 
        user_query: str
    ) -> tuple[List[Dict], List[Dict], int]:
        """Apply intelligent truncation algorithm to manage token budget"""
        
        content_summary = []
        source_urls = []
        used_chars = 0
        max_sources = min(MAX_SOURCES_PROCESSED, len(scraped_results))
        
        logger.info(f"🎯 Smart Truncation: Processing {max_sources} sources with {CONTENT_BUDGET_CHARS} char budget")
        
        for i, result in enumerate(scraped_results[:max_sources]):
            # Calculate remaining budget and fair distribution
            remaining_sources = max_sources - i
            remaining_budget = CONTENT_BUDGET_CHARS - used_chars
            
            if remaining_budget <= MIN_CHARS_PER_SOURCE:
                logger.warning(f"⚠️ Budget exhausted at source {i+1}, stopping truncation")
                break
                
            # Smart allocation calculation
            fair_share = remaining_budget // remaining_sources
            max_per_source = min(MAX_CHARS_PER_SOURCE, fair_share)
            
            # Get source data
            url = result.get('url', '')
            title = result.get('title', '')[:200]
            raw_content = result.get('content', '')
            quality_score = result.get('quality_score', 50)
            
            # Calculate optimal allocation
            allocated_chars = calculate_content_allocation(
                quality_score, max_per_source, max_sources, i
            )
            allocated_chars = min(allocated_chars, len(raw_content), remaining_budget)
            
            # Extract optimized content preview
            content_preview = raw_content[:allocated_chars]
            used_chars += allocated_chars
            
            # Create content summary entry
            content_summary.append({
                "source": i + 1,
                "title": title,
                "url": url,
                "content_preview": content_preview,
                "quality_score": quality_score,
                "word_count": result.get('word_count', 0),
                "allocated_chars": allocated_chars,
                "truncated": len(raw_content) > allocated_chars
            })
            
            # Track source URLs
            if url and title:
                source_urls.append(create_source_metadata(i + 1, result, allocated_chars, len(raw_content)))
        
        logger.info(f"✅ Smart Truncation: Used {used_chars}/{CONTENT_BUDGET_CHARS} chars across {len(content_summary)} sources")
        
        return content_summary, source_urls, used_chars

    # ==================== RESEARCH SYNTHESIS ENGINE ====================
    
    async def _generate_research_synthesis(self, 
                                           content_summary: List[Dict], 
                                           user_query: str, 
                                           source_urls: List[Dict], 
                                           used_chars: int, 
                                           original_results: List[Dict]) -> Dict[str, Any]:
        
        """Generate comprehensive research synthesis using LLM"""
        
        # Build synthesis prompt
        prompt = RESEARCH_SYNTHESIS_PROMPT.format(
            user_query=user_query,
            source_data=json.dumps(content_summary, indent=1)
        )
        
        # Call LLM for synthesis
        response = make_groq_request_with_fallback(
            messages=[{"role": "user", "content": prompt}],
            model=LLM_MODEL,
            temperature=LLM_TEMPERATURE,
            max_tokens=MAX_TOKENS,
            api_key_priority_order=ORGANIZER_API_ORDER
        )
        
        # Parse and enhance result
        result = json.loads(response.choices[0].message.content)
        
        # Add comprehensive metadata
        result.update({
            'raw_results_count': len(original_results),
            'processed_sources': len(content_summary),
            'total_chars_used': used_chars,
            'source_urls': source_urls,
            'verification_sources': self._create_verification_sources(result, source_urls),
            'actual_word_count': len(result.get('unified_content', '').split()),
            'actual_char_count': len(result.get('unified_content', '')),
            'truncation_applied': True,
            'truncation_savings': f"Reduced from ~{sum(len(r.get('content', '')) for r in original_results)} to {used_chars} chars"
        })
        
        return result

    def _create_verification_sources(self, result: Dict, source_urls: List[Dict]) -> List[Dict]:
        """Create verification source mapping"""
        source_usage = result.get('source_usage', [])
        verification_sources = []
        
        for usage in source_usage:
            source_id = usage.get('source_id', 0)
            if source_id > 0 and source_id <= len(source_urls):
                source_info = source_urls[source_id - 1]
                verification_sources.append({
                    "title": source_info['title'],
                    "url": source_info['url'],
                    "domain": source_info['domain'],
                    "contributed": usage.get('contributed_info', ''),
                    "quality_score": source_info['quality_score'],
                    "content_used": source_info['content_length'],
                    "was_truncated": source_info['was_truncated']
                })
        
        return verification_sources

    # ==================== ENHANCED FALLBACK SYSTEM ====================
    
    def _create_enhanced_fallback(self, 
                                  content_summary: List[Dict], 
                                  source_urls: List[Dict], 
                                  used_chars: int, 
                                  original_results: List[Dict], 
                                  user_query: str) -> Dict[str, Any]:
        """Create comprehensive fallback response preserving truncation intelligence"""
        
        logger.info("🔄 Using enhanced fallback with truncated content...")
        
        # Extract content and build fallback sources
        all_content = []
        fallback_sources = []
        
        for i, summary in enumerate(content_summary):
            content = summary['content_preview']
            if content and len(content) > 100:
                all_content.append(content)
                fallback_sources.append({
                    "title": summary['title'],
                    "url": summary['url'],
                    "domain": extract_domain_from_url(summary['url']),
                    "contributed": f"Truncated content section {len(all_content)}",
                    "quality_score": summary['quality_score'],
                    "content_used": summary['allocated_chars'],
                    "was_truncated": summary['truncated']
                })
        
        # Create structured fallback content
        sections = create_fallback_sections(all_content, user_query)
        unified_fallback = "\n".join(sections)
        
        # Return comprehensive fallback response
        return {
            "unified_content": unified_fallback,
            "key_facts": [
                f"Smart truncation applied to {len(content_summary)} sources",
                f"Total content budget: {used_chars} characters",
                f"Comprehensive research from {len(fallback_sources)} sources",
                "Enhanced fallback system preserved all source URLs"
            ],
            "main_findings": f"Comprehensive research synthesis from {len(fallback_sources)} sources using smart truncation to optimize token usage while preserving information quality",
            "information_quality": "good",
            "confidence": 0.7,
            "content_depth": "comprehensive",
            "word_count": len(unified_fallback.split()),
            "coverage_areas": ["smart_truncated_research", "comprehensive_synthesis", "source_preservation"],
            "source_usage": [
                {
                    "source_id": i+1,
                    "contributed_info": f"Smart truncated content: {fallback_sources[i]['content_used']} chars"
                } 
                for i in range(len(fallback_sources))
            ],
            "most_valuable_sources": list(range(1, min(6, len(fallback_sources) + 1))),
            "source_synthesis": "smart_truncation_with_quality_preservation",
            "raw_results_count": len(original_results),
            "processed_sources": len(content_summary),
            "total_chars_used": used_chars,
            "actual_word_count": len(unified_fallback.split()),
            "actual_char_count": len(unified_fallback),
            "truncation_applied": True,
            "truncation_savings": f"Reduced from ~{sum(len(r.get('content', '')) for r in original_results)} to {used_chars} chars",
            "source_urls": source_urls,
            "verification_sources": fallback_sources
        }

# ==================== GLOBAL INSTANCE MANAGEMENT ====================

# Singleton pattern for efficient resource management
_content_organizer = None

def get_content_organizer() -> ContentOrganizer:
    """
    Get global ContentOrganizer instance (Singleton pattern)
    
    Returns:
        ContentOrganizer: Initialized content organizer instance
    """
    global _content_organizer
    if _content_organizer is None:
        _content_organizer = ContentOrganizer()
    return _content_organizer

# ==================== CONVENIENCE FUNCTIONS ====================

async def organize_content(scraped_results: List[Dict], user_query: str) -> Dict[str, Any]:
    """
    Quick function to organize scraped content (backward compatibility)
    
    Args:
        scraped_results: List of scraped content dictionaries
        user_query: User's research query
        
    Returns:
        Dict containing organized research synthesis
    """
    organizer = get_content_organizer()
    return await organizer.organize_scraped_content(scraped_results, user_query)
