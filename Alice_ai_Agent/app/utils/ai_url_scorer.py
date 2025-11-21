import os
import asyncio
import logging
from typing import List, Dict, Optional
from dotenv import load_dotenv
from groq import AsyncGroq

logger = logging.getLogger(__name__)

class AIURLScorer:
    """AI-powered URL relevance scorer using Llama models."""
    
    def __init__(self):
        # Load environment from multiple possible locations
        self._load_environment()
        self.primary_client = None
        self.fallback_client = None
        self.initialize_clients()
    
    def _load_environment(self):
        """Load environment variables from various locations."""
        # Try loading from current directory
        load_dotenv()
        
        # Try loading from Alice AI agent folder
        alice_env_path = os.path.join(os.path.dirname(__file__), '..', '..', '.env')
        if os.path.exists(alice_env_path):
            load_dotenv(alice_env_path)
            
        # Try loading from project root
        root_env_path = os.path.join(os.path.dirname(__file__), '..', '..', '..', '..', '.env')
        if os.path.exists(root_env_path):
            load_dotenv(root_env_path)
    
    def initialize_clients(self):
        """Initialize Groq clients for AI models."""
        try:
            api_key = os.getenv("GROQ_API_KEY")
            if not api_key:
                logger.warning("GROQ_API_KEY not found. AI URL scoring will be disabled.")
                return
                
            self.primary_client = AsyncGroq(api_key=api_key)
            self.fallback_client = AsyncGroq(api_key=api_key)
            logger.info("AI URL scorer clients initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize AI clients: {e}")
    
    async def score_urls(self, query: str, urls: List[Dict[str, str]]) -> List[Dict[str, str]]:
        """Score URLs based on relevance to query using AI."""
        if not self.primary_client:
            logger.warning("AI clients not available, returning URLs without scoring")
            return urls
        
        try:
            scored_urls = []
            
            for url_info in urls:
                try:
                    score = await self._score_single_url(query, url_info)
                    url_info['ai_score'] = score
                    url_info['ai_reasoning'] = f"Relevance score: {score}/10"
                    scored_urls.append(url_info)
                except Exception as e:
                    logger.error(f"Error scoring URL {url_info.get('url', '')}: {e}")
                    url_info['ai_score'] = 5.0  # Default neutral score
                    url_info['ai_reasoning'] = "Scoring failed, using default"
                    scored_urls.append(url_info)
            
            # Sort by AI score descending
            scored_urls.sort(key=lambda x: x.get('ai_score', 0), reverse=True)
            
            logger.info(f"Scored {len(scored_urls)} URLs for query: {query}")
            return scored_urls
            
        except Exception as e:
            logger.error(f"Error in AI URL scoring: {e}")
            return urls
    
    async def _score_single_url(self, query: str, url_info: Dict[str, str]) -> float:
        """Score a single URL's relevance to the query."""
        try:
            # First try with primary model (Llama 3.3 70B)
            try:
                return await self._get_score_from_model(
                    query, url_info, "llama-3.3-70b-versatile"
                )
            except Exception as e:
                logger.warning(f"Primary model failed, trying fallback: {e}")
                
            # Fallback to Llama Scout 
            return await self._get_score_from_model(
                query, url_info, "llama-4-scout-17b-16e-instruct"
            )
            
        except Exception as e:
            logger.error(f"Both AI models failed for URL scoring: {e}")
            return 5.0  # Default neutral score
    
    async def _get_score_from_model(self, query: str, url_info: Dict[str, str], model: str) -> float:
        """Get relevance score from specific AI model."""
        title = url_info.get('title', '')
        url = url_info.get('url', '')
        description = url_info.get('description', '')
        
        prompt = f"""
        Analyze the relevance of this URL to the search query.
        
        Query: "{query}"
        
        URL Information:
        - Title: {title}
        - URL: {url}
        - Description: {description}
        
        Rate the relevance on a scale of 1-10 where:
        - 10 = Extremely relevant, directly answers the query
        - 7-9 = Highly relevant, contains significant information about the query
        - 4-6 = Moderately relevant, related to the topic
        - 1-3 = Barely relevant or off-topic
        
        Respond with ONLY a single number between 1 and 10.
        """
        
        client = self.primary_client if model == "llama-3.3-70b-versatile" else self.fallback_client
        
        response = await client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
            max_tokens=10
        )
        
        score_text = response.choices[0].message.content.strip()
        
        # Extract numeric score
        try:
            score = float(score_text)
            return max(1.0, min(10.0, score))  # Clamp to 1-10 range
        except ValueError:
            logger.warning(f"Invalid score format from AI: {score_text}")
            return 5.0  # Default neutral score
    
    async def get_search_insights(self, query: str, scored_urls: List[Dict[str, str]]) -> Dict[str, str]:
        """Generate AI insights about the search results."""
        if not self.primary_client or not scored_urls:
            return {
                "summary": "Search completed",
                "recommendations": "Review the search results for relevant information.",
                "quality_assessment": "Standard search results"
            }
        
        try:
            top_urls = scored_urls[:5]  # Analyze top 5 URLs
            
            url_summaries = []
            for url in top_urls:
                url_summaries.append(f"- {url.get('title', 'Untitled')} (Score: {url.get('ai_score', 0)}/10)")
            
            prompt = f"""
            Analyze this search query and results to provide insights.
            
            Query: "{query}"
            
            Top Results:
            {chr(10).join(url_summaries)}
            
            Provide insights in this JSON format:
            {{
                "summary": "Brief summary of what was found",
                "recommendations": "Recommendations for the user",
                "quality_assessment": "Assessment of result quality"
            }}
            
            Keep responses concise and helpful.
            """
            
            response = await self.primary_client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=200
            )
            
            import json
            try:
                insights = json.loads(response.choices[0].message.content.strip())
                return insights
            except json.JSONDecodeError:
                # Fallback to simple parsing
                content = response.choices[0].message.content.strip()
                return {
                    "summary": "AI analysis completed",
                    "recommendations": content[:100] + "..." if len(content) > 100 else content,
                    "quality_assessment": "See recommendations for details"
                }
                
        except Exception as e:
            logger.error(f"Error generating search insights: {e}")
            return {
                "summary": "Search completed successfully",
                "recommendations": "Review the search results for relevant information.",
                "quality_assessment": "Standard search results provided"
            }