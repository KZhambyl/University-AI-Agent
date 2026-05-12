import requests
from langchain.tools import tool
from schemas import CountryListOutput, UniversitySearchInput, CurrencyRateInput
from openai import OpenAI
import urllib.parse



@tool
def resolve_countries(user_description: str) -> dict:
    """Convert a vague user description (e.g. 'warm country', 'Europe', 'Asia', 
    'cheap to live') into a list of specific country names.
    Use this FIRST when the user describes a region or condition instead of naming a specific country.
    Returns a list of country names in English that can be used with other tools."""

    client = OpenAI()
    response = client.beta.chat.completions.parse(
        model = 'gpt-4o-mini',
        messages = [
            {"role": "system", "content": "You convert user descriptions of where to study into a list of 3-5 specific countries in English. Return country names exactly as they appear on Wikipedia."},
            {"role": "user", "content": user_description}
        ],
        response_format = CountryListOutput,
        temperature=0.3
    )
    parsed = response.choices[0].message.parsed

    return {
        "countries": parsed.countries,
        "reasoning": parsed.reasoning,
    }

@tool(args_schema = UniversitySearchInput)
def search_universities(country: str, limit: int = 3) -> dict:
    """Search universities in a given country. Returns a list of universities with names and websites."""
    try:
        response = requests.get(
            "http://universities.hipolabs.com/search",
            params={"country": country},
            timeout=10,
        )
        response.raise_for_status()
        data = response.json()

        if not data:
            return {"error": f"No universities found in {country}", "universities": []}
        
        universities = [
            {
                "name": uni["name"],
                "website": uni["web_pages"][0] if uni.get("web_pages") else None,
                "country": uni["country"]
            } for uni in data[:limit]
        ]
        return {"universities": universities, "count": len(universities)}
    
    except requests.exceptions.RequestException as e:
        return {'error': f"Failed to fetch universities: {str(e)}", "universities": []}
    
@tool
def get_univeristy_summary(university_name: str) -> dict:
    """Get a brief description of a university from Wikipedia.
    Use this AFTER finding universities, to provide context to the user."""
    
    search_url = "https://en.wikipedia.org/w/api.php"
    search_params = {
        "action": "opensearch",
        "search": university_name,
        "limit": 1,
        "format": "json",
    }
    headers = {"User-Agent": "UniversityAgent/1.0 (student project)"}

    try:
        srch_resp = requests.get(search_url, search_params, headers=headers, timeout=10)
        srch_resp.raise_for_status()
        srch_data = srch_resp.json()

        if not srch_data[1]:
            return {"summary": None, "error": f"No Wikipedia article found for '{university_name}'"}
        
        article = srch_data[1][0]

        encoded = urllib.parse.quote(article.replace(" ", "_"))
        summary_url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{encoded}"
        summary_resp  = requests.get(summary_url, headers=headers, timeout=10)

        if summary_resp.status_code == 404:
            return {"summary": None, "error": "Article not found"}
        summary_resp.raise_for_status()

        summary_data = summary_resp.json()
        
        return {
            "summary": summary_data.get("extract"),
            "title": summary_data.get("title"),
            "url": summary_data.get("content_urls", {}).get("desktop", {}).get("page"),
        }
    
    except requests.exceptions.RequestException as e:
        return {"summary": None, "error": f"Wikipedia request failed: {str(e)}"}
    


@tool(args_schema=CurrencyRateInput)
def get_country_currency_rate(country: str) -> dict:
    """Get the exchange rate of a country's local currency to Kazakhstani Tenge (KZT).
    
    Returns how many KZT equals 1 unit of the local currency.
    For example, for Germany it returns the EUR to KZT rate (e.g. 1 EUR = 580 KZT).
    
    Use this whenever you need to show the user the local currency of a country
    and its current exchange rate to KZT. ALWAYS call this for every country
    you recommend universities in."""
    
    try:
        country_resp = requests.get(
            f"https://restcountries.com/v3.1/name/{country}",
            params={"fullText": "false"},
            timeout=10,
        )
        country_resp.raise_for_status()
        country_data = country_resp.json()[0]

        currencies = country_data.get("currencies", {})
        if not currencies:
            return {"error": f"No currency info for {country}"}
        
        currency_code = list(currencies.keys())[0]
        currency_name = currencies[currency_code].get("name", currency_code)

        if currency_code == "KZT":
            return {
                "country": country,
                "currency_code": "KZT",
                "currency_name": "Kazakhstani Tenge",
                "exchange_rate_to_kzt": 1.0,
                "human_readable": "Local currency is already KZT (1 KZT = 1 KZT)",
            }
        
        fx_resp = requests.get(
            f"https://open.er-api.com/v6/latest/{currency_code}",
            timeout=10,
        )
        fx_resp.raise_for_status()
        fx_data = fx_resp.json()
        
        if "rates" not in fx_data or "KZT" not in fx_data["rates"]:
            return {"error": f"No KZT rate available for {currency_code}"}
        
        rate = fx_data["rates"]["KZT"]
        
        return {
            "country": country,
            "currency_code": currency_code,
            "currency_name": currency_name,
            "exchange_rate_to_kzt": round(rate, 2),
            "human_readable": f"1 {currency_code} = {rate:.2f} KZT",
            "exchange_date": fx_data.get("time_last_update_utc", "unknown"),
        }
    
    except requests.exceptions.RequestException as e:
        return {"error": f"Request failed: {str(e)}"}
    except (KeyError, IndexError) as e:
        return {"error": f"Unexpected API response: {str(e)}"}
