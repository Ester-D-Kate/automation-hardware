"""
LLM URL Ranker using Groq Cloud
Uses Ollama 70B to rank URLs by relevance to user query
"""

import json
from .search_config import GROQ_API_KEY, LLM_MODEL, LLM_TEMPERATURE, MAX_RANKING_URLS

# Try to import groq, handle if not installed
try:
    from groq import Groq
    GROQ_AVAILABLE = True
except ImportError:
    GROQ_AVAILABLE = False
    print("⚠️ Groq not installed. Install with: pip install groq")

async def rank_urls_with_llm(search_results, user_query, required_count=5):
    """
    Use LLM to rank URLs by relevance to user query
    
    Args:
        search_results: List of search results with title, url, snippet
        user_query: Original user query
        required_count: How many top results to return
    
    Returns:
        List of ranked results (best first)
    """
    if not GROQ_AVAILABLE or not GROQ_API_KEY:
        print("⚠️ LLM ranking not available, using simple ranking")
        return simple_rank_urls(search_results, user_query, required_count)
    
    print(f"🧠 Ranking {len(search_results)} URLs with LLM for query: '{user_query}'")
    
    # Limit URLs sent to LLM to avoid token limits
    urls_to_rank = search_results[:MAX_RANKING_URLS]
    
    try:
        # Initialize Groq client
        client = Groq(api_key=GROQ_API_KEY)
        
        # Prepare URLs for LLM
        url_data = []
        for i, result in enumerate(urls_to_rank):
            url_data.append({
                'id': i,
                'title': result.get('title', ''),
                'url': result.get('url', ''),
                'snippet': result.get('snippet', '')
            })
        
        # Create ranking prompt
        ranking_prompt = create_ranking_prompt(user_query, url_data, required_count)
        
        # Call LLM
        print("🤖 Asking LLM to rank URLs...")
        response = client.chat.completions.create(
            model=LLM_MODEL,
            messages=[
                {
                    "role": "system",
                    "content": "You are an expert at ranking web search results by relevance to user queries. Always respond with valid JSON."
                },
                {
                    "role": "user", 
                    "content": ranking_prompt
                }
            ],
            temperature=LLM_TEMPERATURE,
            max_tokens=1000
        )
        
        # Parse LLM response
        llm_output = response.choices[0].message.content.strip()
        ranked_results = parse_llm_ranking(llm_output, search_results)
        
        print(f"✅ LLM ranked {len(ranked_results)} URLs")
        return ranked_results[:required_count]
        
    except Exception as e:
        print(f"❌ LLM ranking failed: {e}")
        print("🔄 Falling back to simple ranking")
        return simple_rank_urls(search_results, user_query, required_count)

def create_ranking_prompt(user_query, url_data, required_count):
    """
    Create the prompt for LLM URL ranking
    """
    prompt = f"""
Rank these web search results by relevance to the user query: "{user_query}"

Return the top {required_count} most relevant results as JSON array with this format:
[
    {{"id": 0, "relevance_score": 95, "reason": "why this is most relevant"}},
    {{"id": 2, "relevance_score": 85, "reason": "why this is second most relevant"}},
    ...
]

Consider:
1. Title relevance to the query
2. Snippet content match
3. URL domain authority and trustworthiness
4. How well the content would answer the user's question

Search Results to rank:
"""
    
    for item in url_data:
        prompt += f"""
ID: {item['id']}
Title: {item['title']}
URL: {item['url']}
Snippet: {item['snippet']}
---
"""
    
    prompt += f"\nReturn only the JSON array with the top {required_count} most relevant results."
    return prompt

def parse_llm_ranking(llm_output, original_results):
    """
    Parse LLM ranking response and return ordered results
    Enhanced to handle Ollama 3.3 70B output format variations
    """
    try:
        print(f"🔍 Debug LLM Output (first 200 chars): {llm_output[:200]}")
        
        # Multiple strategies to extract JSON
        json_str = None
        
        # Strategy 1: Look for [ ] array
        start_idx = llm_output.find('[')
        end_idx = llm_output.rfind(']') + 1
        if start_idx >= 0 and end_idx > start_idx:
            json_str = llm_output[start_idx:end_idx]
        
        # Strategy 2: Look for { } object that might contain an array
        elif '{' in llm_output and '}' in llm_output:
            start_idx = llm_output.find('{')
            end_idx = llm_output.rfind('}') + 1
            json_str = llm_output[start_idx:end_idx]
        
        # Strategy 3: Try to extract any JSON-like structure
        else:
            import re
            # Look for patterns like {"id": 0, "relevance_score": 95}
            json_pattern = r'\[.*?\]|\{.*?\}'
            matches = re.findall(json_pattern, llm_output, re.DOTALL)
            if matches:
                json_str = matches[0]
        
        if json_str:
            print(f"🔍 Extracted JSON: {json_str[:100]}...")
            ranking_data = json.loads(json_str)
            
            # Handle both array and object formats
            if isinstance(ranking_data, dict) and 'results' in ranking_data:
                ranking_data = ranking_data['results']
            elif not isinstance(ranking_data, list):
                raise ValueError(f"Unexpected JSON format: {type(ranking_data)}")
            
            # Build ranked results
            ranked_results = []
            for item in ranking_data:
                result_id = item.get('id')
                relevance_score = item.get('relevance_score', 0)
                reason = item.get('reason', '')
                
                if 0 <= result_id < len(original_results):
                    result = original_results[result_id].copy()
                    result['relevance_score'] = relevance_score
                    result['ranking_reason'] = reason
                    ranked_results.append(result)
            
            return ranked_results
        else:
            raise ValueError("No valid JSON found in LLM response")
            
    except Exception as e:
        print(f"❌ Error parsing LLM ranking: {e}")
        print(f"❌ Full LLM output: {llm_output}")
        return simple_rank_urls(original_results, "", len(original_results))

def simple_rank_urls(search_results, user_query, required_count):
    """
    Simple fallback ranking when LLM is not available
    Based on title and snippet relevance
    """
    print("📊 Using simple ranking algorithm")
    
    query_words = user_query.lower().split()
    
    # Score each result
    for result in search_results:
        score = 0
        title = result.get('title', '').lower()
        snippet = result.get('snippet', '').lower()
        
        # Score based on query word matches
        for word in query_words:
            if word in title:
                score += 10  # Title matches are worth more
            if word in snippet:
                score += 5   # Snippet matches
        
        # Bonus for shorter, cleaner titles
        if result.get('title', ''):
            if len(result['title']) < 100:
                score += 2
        
        result['relevance_score'] = score
        result['ranking_reason'] = f"Simple scoring: {score} points"
    
    # Sort by score
    ranked = sorted(search_results, key=lambda x: x.get('relevance_score', 0), reverse=True)
    
    print(f"📊 Simple ranking completed for {len(ranked)} URLs")
    return ranked[:required_count]

def print_ranking_results(ranked_results):
    """
    Print the ranking results in a readable format
    """
    print(f"\n🏆 Top {len(ranked_results)} Ranked URLs:")
    for i, result in enumerate(ranked_results, 1):
        print(f"   {i}. [{result.get('relevance_score', 0)}] {result.get('title', 'No title')}")
        print(f"      URL: {result.get('url', '')}")
        print(f"      Reason: {result.get('ranking_reason', 'No reason')}")
        print()