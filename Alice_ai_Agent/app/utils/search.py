import requests
import json
from bs4 import BeautifulSoup
import re
import datetime
import logging
from typing import Dict, List, Optional
from utils.config import SEARXNG_URL

logger = logging.getLogger(__name__)

def perform_search(query: str) -> Dict:
    """Perform an internet search, fetch content from top URLs, and compress it for LLM consumption"""
    logger.info(f"Performing search for query: {query}")
    
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/100.0.4896.127 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Referer": "http://192.168.1.4:8888/",
            "DNT": "1"
        }
        
        params = {
            "q": query,
            "categories": "general"
        }
        
        logger.info(f"Requesting search from: {SEARXNG_URL}")
        
        search_response = requests.get(
            SEARXNG_URL,
            params=params,
            headers=headers,
            timeout=10
        )
        
        if not search_response.ok:
            logger.error(f"Search API returned error status: {search_response.status_code}")
            return get_mock_search_results(query)
            
        soup = BeautifulSoup(search_response.text, 'html.parser')
        
        direct_answer = None
        answer_elements = soup.select('#answers .answer')

        if answer_elements and len(answer_elements) > 0:
            answer = answer_elements[0]
            answer_text = answer.get_text(strip=True)
            answer_url_elem = answer.select_one('.answer-url')
            answer_url = answer_url_elem.get_text(strip=True) if answer_url_elem else ""
            
            direct_answer = {
                "text": answer_text,
                "source": answer_url
            }
        
        urls = []
        result_elements = soup.select('article.result')
        if result_elements:
            for i, result in enumerate(result_elements[:5]):  # Get up to 5 results
                title_elem = result.select_one('h3 a')
                if title_elem and 'href' in title_elem.attrs:
                    title = title_elem.get_text(strip=True)
                    url = title_elem['href']
                    urls.append({"title": title, "url": url})
        
        if not urls and not direct_answer:
            suggestions_elem = soup.select('#suggestions .suggestion')
            if suggestions_elem:
                suggestions = [elem['value'].strip('• ') for elem in suggestions_elem if 'value' in elem.attrs][:5]
                formatted_suggestions = "Related searches: " + ", ".join(suggestions)
                return {
                    "status": "success",
                    "results": f"No direct results found for '{query}'. {formatted_suggestions}"
                }
            else:
                return get_mock_search_results(query)
        
        content_results = []
        
        for url_info in urls:
            try:
                logger.info(f"Fetching content from: {url_info['url']}")
                page_response = requests.get(url_info['url'], headers=headers, timeout=5)
                if page_response.ok:
                    page_soup = BeautifulSoup(page_response.text, 'html.parser')
                    
                    for element in page_soup.select('script, style, nav, footer, header, aside, .ads, .comments, .sidebar'):
                        element.decompose()
                    main_content = ""
                    content_selectors = [
                        'main', 'article', '.content', '.post-content', '.entry-content', 
                        '#content', '.main-content', '.article-body', '.post-body'
                    ]

                    for selector in content_selectors:
                        content_area = page_soup.select_one(selector)
                        if content_area:
                            main_content = content_area.get_text(separator=' ', strip=True)
                            break

                    if not main_content and page_soup.body:
                        main_content = page_soup.body.get_text(separator=' ', strip=True)
                    
                    if main_content:
                        main_content = re.sub(r'\s+', ' ', main_content).strip()
                        
                        if len(main_content) > 1000:
                            main_content = main_content[:997] + "..."
                        
                        content_results.append({
                            "title": url_info["title"],
                            "url": url_info["url"],
                            "content": main_content
                        })

            except Exception as e:
                logger.error(f"Error fetching content from {url_info['url']}: {e}")
                
                content_results.append({
                    "title": url_info["title"],
                    "url": url_info["url"],
                    "content": "Content unavailable"
                })
        
        formatted_results = ""
    
        if direct_answer:
            formatted_results += f"DIRECT ANSWER: {direct_answer['text']}\n"
            formatted_results += f"Source: {direct_answer['source']}\n\n"
        
        if content_results:
            formatted_results += "CONTENT FROM TOP SOURCES:\n\n"
            
            for i, result in enumerate(content_results):
                formatted_results += f"SOURCE {i+1}: {result['title']}\n"
                formatted_results += f"URL: {result['url']}\n"
                formatted_results += f"CONTENT SUMMARY: {result['content']}\n\n"
        
        if formatted_results:
            return {
                "status": "success",
                "results": formatted_results.strip()
            }
        else:
            return get_mock_search_results(query)
            
    except Exception as e:
        logger.error(f"Search error: {e}")
        return get_mock_search_results(query)
    
def get_mock_search_results(query: str) -> Dict:
    """Generate mock search results based on the query"""
    logger.info(f"Using mock search results for query: {query}")
    
    if "weather" in query.lower() or "temperature" in query.lower():
        location = "Amritsar"
        if "in " in query.lower():
            parts = query.lower().split("in ")
            if len(parts) > 1:
                location_parts = parts[1].split()
                location = ' '.join([p.capitalize() for p in location_parts[:2] if p not in ["the", "current", "today", "now"]])
        hour = datetime.datetime.now().hour
        
        if 5 <= hour < 12:
            time_of_day = "morning"
            temp_modifier = -2
        elif 12 <= hour < 17:
            time_of_day = "afternoon"
            temp_modifier = 3
        elif 17 <= hour < 20:
            time_of_day = "evening"
            temp_modifier = 0
        else:
            time_of_day = "night"
            temp_modifier = -5
        base_temp = 30 
        current_temp = base_temp + temp_modifier

        if location.lower() == "amritsar":
            return {
                "status": "success",
                "results": f"Current Weather in Amritsar, Punjab (Mock Data):\n\nTemperature: {current_temp}°C ({int(current_temp*1.8+32)}°F)\nCondition: Partly Cloudy\nHumidity: 65%\nWind: 12 km/h\n\nForecast:\n- Today: High of {current_temp+2}°C, Low of {current_temp-6}°C, Partly Cloudy\n- Tomorrow: High of {current_temp+1}°C, Low of {current_temp-7}°C, Mostly Sunny\n\nSource: AccuWeather (Mock Data)\nhttps://www.accuweather.com/en/in/amritsar/189473/weather-forecast/189473"
            }
        else:
            return {
                "status": "success",
                "results": f"Current Weather in {location} (Mock Data):\n\nTemperature: {current_temp-2}°C ({int((current_temp-2)*1.8+32)}°F)\nCondition: Mostly Sunny\nHumidity: 60%\nWind: 10 km/h\n\nForecast:\n- Today: High of {current_temp}°C, Low of {current_temp-8}°C, Clear Skies\n- Tomorrow: High of {current_temp+1}°C, Low of {current_temp-7}°C, Partly Cloudy\n\nSource: AccuWeather (Mock Data)\nhttps://www.accuweather.com/en/in/{location.lower().replace(' ', '-')}/weather-forecast/"
            }

    elif "time" in query.lower():
        now = datetime.datetime.now()
        return {
            "status": "success",
            "results": f"Current Time (Mock Data):\n\nLocal Time: {now.strftime('%I:%M %p')}\nDate: {now.strftime('%A, %B %d, %Y')}\n\nTime Zones:\n- IST (India): {(now).strftime('%I:%M %p')}\n- UTC/GMT: {(now - datetime.timedelta(hours=5, minutes=30)).strftime('%I:%M %p')}\n- EST (US East): {(now - datetime.timedelta(hours=9, minutes=30)).strftime('%I:%M %p')}\n\nSource: TimeAndDate.com (Mock Data)\nhttps://www.timeanddate.com/worldclock/"
        }

    else:
        clean_query = query.lower().replace(" ", "-")
        return {
            "status": "success",
            "results": f"Search Results for '{query}' (Mock Data):\n\n1. {query.title()} - An Overview\nComprehensive information about {query} including history, applications, and recent developments.\nhttps://en.wikipedia.org/wiki/{clean_query}\n\n2. Understanding {query.title()}\nA beginner's guide to {query} with practical examples and explanations.\nhttps://www.britannica.com/topic/{clean_query}\n\n3. The Complete Guide to {query.title()}\nEverything you need to know about {query} in one place.\nhttps://www.howtogeek.com/guide/{clean_query}"
        }