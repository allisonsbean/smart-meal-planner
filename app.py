import streamlit as st
import requests
import pandas as pd
from datetime import datetime, timedelta
import json
import base64
import plotly.express as px
import plotly.graph_objects as go
from typing import Dict, List, Optional
import random
from collections import defaultdict
import calendar
from config import *

# Page configuration
st.set_page_config(
    page_title="Smart Family Meal Planner",
    page_icon="🍽️",
    layout="wide"
)

# Custom CSS for better styling
st.markdown("""
<style>
.recipe-card {
border: 1px solid #ddd;
border-radius: 8px;
padding: 1rem;
margin: 0.5rem 0;
background-color: #f8f9fa;
}
.sale-item {
background-color: #fff3cd;
border: 1px solid #ffeaa7;
border-radius: 4px;
padding: 0.5rem;
margin: 0.25rem 0;
}
.nutrition-info {
background-color: #e7f3ff;
border-radius: 4px;
padding: 0.5rem;
}
</style>
""", unsafe_allow_html=True)

@st.cache_data(ttl=3600)
def get_kroger_token():
    """Get OAuth token for Kroger API"""
    try:
        credentials = f"{KROGER_CLIENT_ID}:{KROGER_CLIENT_SECRET}"
        encoded_credentials = base64.b64encode(credentials.encode()).decode()
        
        url = f"{KROGER_BASE_URL}/v1/connect/oauth2/token"
        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "Authorization": f"Basic {encoded_credentials}"
        }
        data = {
            "grant_type": "client_credentials",
            "scope": "product.compact"
        }
        
        response = requests.post(url, headers=headers, data=data)
        if response.status_code == 200:
            return response.json()["access_token"]
        else:
            st.error(f"Failed to get Kroger token: {response.status_code}")
            return None
    except Exception as e:
        st.error(f"Error getting Kroger token: {str(e)}")
        return None

@st.cache_data(ttl=3600)
def find_kroger_store(zip_code):
    """Find nearest Kroger store"""
    token = get_kroger_token()
    if not token:
        return None
    
    try:
        url = f"{KROGER_BASE_URL}/v1/locations"
        headers = {"Authorization": f"Bearer {token}"}
        params = {
            "filter.zipCode.near": zip_code,
            "filter.chain": "Kroger",
            "filter.limit": 1
        }
        
        response = requests.get(url, headers=headers, params=params)
        if response.status_code == 200:
            data = response.json()
            if data["data"]:
                return data["data"][0]
        return None
    except Exception as e:
        st.error(f"Error finding store: {str(e)}")
        return None
@st.cache_data(ttl=1800)
def search_kroger_products(search_term, location_id=None):
    """Search for products in Kroger"""
    token = get_kroger_token()
    if not token:
        return []
    
    try:
        url = f"{KROGER_BASE_URL}/v1/products"
        headers = {"Authorization": f"Bearer {token}"}
        params = {
            "filter.term": search_term,
            "filter.limit": 20
        }
        
        if location_id:
            params["filter.locationId"] = location_id
        
        response = requests.get(url, headers=headers, params=params)
        if response.status_code == 200:
            data = response.json()
            return data.get("data", [])
        else:
            return []
    except Exception as e:
        return []

def extract_sale_items():
    """Extract items that are on sale"""
    if 'kroger_store' not in st.session_state or not st.session_state.kroger_store:
        return []
    
    sale_categories = ["chicken", "turkey", "salmon", "ground turkey", "sweet potato", "broccoli"]
    sale_items = []
    
    for category in sale_categories:
        products = search_kroger_products(category, st.session_state.kroger_store["locationId"])
        for product in products:
            if product.get("items"):
                item = product["items"][0]
                price_info = item.get("price", {})
                if price_info.get("promo") and price_info.get("regular"):
                    if price_info["promo"] < price_info["regular"]:
                        sale_items.append({
                            "name": product.get("description", "Unknown"),
                            "regular_price": price_info["regular"],
                            "sale_price": price_info["promo"],
                            "savings": round(price_info["regular"] - price_info["promo"], 2),
                            "category": category.title(),
                            "discount_percentage": round(((price_info["regular"] - price_info["promo"]) / price_info["regular"]) * 100, 1)
                        })
    
    return sale_items

class PurchaseTimingAnalyzer:
    """Analyze when to buy items based on sales"""
    
    def __init__(self):
        self.buy_thresholds = {
            "excellent": 25,
            "good": 15,
            "modest": 8
        }
    
    def get_recommendation(self, item_name: str, discount_percentage: float) -> dict:
        """Get purchase recommendation based on discount percentage"""
        if discount_percentage >= self.buy_thresholds["excellent"]:
            return {
                "action": "🛒 Buy Now & Stock Up",
                "reason": f"Excellent {discount_percentage}% discount",
                "confidence": "High",
                "timing": "Great deal - buy extra for meal prep"
            }
        elif discount_percentage >= self.buy_thresholds["good"]:
            return {
                "action": "🛒 Buy for This Week",
                "reason": f"Good {discount_percentage}% discount", 
                "confidence": "Medium",
                "timing": "Good price for immediate use"
            }
        elif discount_percentage >= self.buy_thresholds["modest"]:
            return {
                "action": "🤔 Consider If Needed",
                "reason": f"Modest {discount_percentage}% discount",
                "confidence": "Medium",
                "timing": "Buy if you need it this week"
            }
        else:
            return {
                "action": "⏰ Wait for Better Deal",
                "reason": "Small discount, better deals likely coming",
                "confidence": "Low",
                "timing": "Wait unless urgently needed"
            }
    
    def analyze_weekly_savings(self, sale_items: list) -> dict:
        """Analyze potential weekly savings"""
        total_savings = sum(item['savings'] for item in sale_items)
        high_value_items = [item for item in sale_items if item['discount_percentage'] >= 20]
        
        return {
            "total_possible_savings": total_savings,
            "high_value_count": len(high_value_items),
            "average_discount": sum(item['discount_percentage'] for item in sale_items) / len(sale_items) if sale_items else 0,
            "recommendation": self._get_weekly_strategy(total_savings, len(high_value_items))
        }
    
    def _get_weekly_strategy(self, total_savings: float, high_value_count: int) -> str:
        """Get weekly shopping strategy recommendation"""
        if total_savings > 20:
            return "Great week for savings! Focus on items with 20%+ discounts."
        elif total_savings > 10:
            return "Decent savings available. Consider stocking up on non-perishables."
        else:
            return "Light sales week. Good time to use up what you have at home."
class FamilyPreferencesManager:
    """Manages family food preferences and dislikes"""
    
    def __init__(self):
        self.preferences = {
            "disliked_ingredients": [],
            "loved_ingredients": [],
            "neutral_ingredients": [],
            "never_suggest_again": [],
            "family_favorites": [],
            "dietary_restrictions": [],
            "spice_tolerance": "medium",
            "texture_preferences": {
                "creamy": True,
                "crunchy": True, 
                "spicy": True,
                "sweet": True
            }
        }
        
        self.meal_history = {
            "last_4_weeks": [],
            "ingredient_frequency": defaultdict(int)
        }
    
    def add_dislike(self, ingredient: str):
        """Add ingredient to dislike list"""
        ingredient = ingredient.lower().strip()
        if ingredient not in self.preferences["disliked_ingredients"]:
            self.preferences["disliked_ingredients"].append(ingredient)
            if ingredient in self.preferences["loved_ingredients"]:
                self.preferences["loved_ingredients"].remove(ingredient)
    
    def add_love(self, ingredient: str):
        """Add ingredient to love list"""
        ingredient = ingredient.lower().strip()
        if ingredient not in self.preferences["loved_ingredients"]:
            self.preferences["loved_ingredients"].append(ingredient)
            if ingredient in self.preferences["disliked_ingredients"]:
                self.preferences["disliked_ingredients"].remove(ingredient)
    
    def ban_recipe(self, recipe_title: str):
        """Never suggest this recipe again"""
        if recipe_title not in self.preferences["never_suggest_again"]:
            self.preferences["never_suggest_again"].append(recipe_title)
    
    def add_favorite(self, recipe_title: str):
        """Mark recipe as family favorite"""
        if recipe_title not in self.preferences["family_favorites"]:
            self.preferences["family_favorites"].append(recipe_title)
    
    def recipe_contains_dislikes(self, recipe: dict) -> bool:
        """Check if recipe contains any disliked ingredients"""
        recipe_ingredients = [ing.lower() for ing in recipe.get("all_ingredients", [])]
        
        for disliked in self.preferences["disliked_ingredients"]:
            for recipe_ing in recipe_ingredients:
                if disliked in recipe_ing:
                    return True
        return False
    
    def recipe_is_banned(self, recipe: dict) -> bool:
        """Check if recipe is on the never-suggest list"""
        return recipe["title"] in self.preferences["never_suggest_again"]
    
    def was_served_recently(self, recipe: dict, weeks_back: int = 3) -> bool:
        """Check if we've had this recipe in the last X weeks"""
        recent_meals = self.meal_history["last_4_weeks"][-weeks_back*7:]
        return recipe["title"] in [meal["recipe"] for meal in recent_meals]
    
    def log_meal(self, recipe_title: str, date: str):
        """Record that we served this meal"""
        self.meal_history["last_4_weeks"].append({
            "recipe": recipe_title,
            "date": date
        })
        
        if len(self.meal_history["last_4_weeks"]) > 28:
            self.meal_history["last_4_weeks"] = self.meal_history["last_4_weeks"][-28:]

class SmartMealRotator:
    """Ensures variety in meal suggestions with expanded recipe database"""
    
    def __init__(self, preferences_manager: FamilyPreferencesManager):
        self.prefs = preferences_manager
        self.expanded_recipes = self._create_recipe_database()
    
    def _create_recipe_database(self):
        """Create comprehensive recipe database"""
        return {
            "weekday_breakfast": [
                {
                    "title": "Turkey Sausage and Egg Scramble",
                    "main_ingredients": ["turkey sausage", "eggs", "spinach"],
                    "all_ingredients": ["turkey breakfast sausage", "eggs", "fresh spinach", "bell pepper", "onion", "olive oil"],
                    "time": 8, "calories": 280, "tags": ["high-protein", "healthy"]
                },
                {
                    "title": "Greek Yogurt Parfait with Granola",
                    "main_ingredients": ["greek yogurt", "granola", "berries"],
                    "all_ingredients": ["greek yogurt", "granola", "mixed berries", "honey", "nuts"],
                    "time": 5, "calories": 320, "tags": ["quick", "healthy", "protein"]
                },
                {
                    "title": "Avocado Toast with Turkey Bacon",
                    "main_ingredients": ["whole grain bread", "avocado", "turkey bacon"],
                    "all_ingredients": ["whole grain bread", "avocado", "turkey bacon", "tomato", "lime"],
                    "time": 8, "calories": 350, "tags": ["healthy-fats", "satisfying"]
                },
                {
                    "title": "Smoothie Bowl with Protein",
                    "main_ingredients": ["protein powder", "frozen fruit", "spinach"],
                    "all_ingredients": ["protein powder", "frozen berries", "banana", "spinach", "almond milk", "chia seeds"],
                    "time": 5, "calories": 300, "tags": ["smoothie", "antioxidants"]
                }
            ],
            
            "weekday_lunch": [
                {
                    "title": "Grilled Chicken Caesar Wrap",
                    "main_ingredients": ["grilled chicken", "romaine", "whole wheat tortilla"],
                    "all_ingredients": ["grilled chicken breast", "romaine lettuce", "whole wheat tortilla", "light caesar dressing", "parmesan"],
                    "time": 10, "calories": 380, "tags": ["portable", "high-protein"]
                },
                {
                    "title": "Quinoa Power Bowl",
                    "main_ingredients": ["quinoa", "chickpeas", "vegetables"],
                    "all_ingredients": ["quinoa", "chickpeas", "cucumber", "cherry tomatoes", "feta cheese", "olive oil"],
                    "time": 15, "calories": 420, "tags": ["vegetarian", "complete-protein"]
                },
                {
                    "title": "Turkey and Hummus Wrap",
                    "main_ingredients": ["sliced turkey", "hummus", "vegetables"],
                    "all_ingredients": ["sliced turkey", "hummus", "whole wheat wrap", "lettuce", "cucumber", "red bell pepper"],
                    "time": 5, "calories": 340, "tags": ["quick", "lean-protein"]
                },
                {
                    "title": "Black Bean and Rice Bowl",
                    "main_ingredients": ["black beans", "brown rice", "salsa"],
                    "all_ingredients": ["black beans", "brown rice", "salsa", "corn", "bell peppers", "cilantro"],
                    "time": 12, "calories": 360, "tags": ["vegetarian", "fiber-rich"]
                }
            ],
            
            "weekday_dinner": [
                {
                    "title": "Baked Salmon with Roasted Vegetables",
                    "main_ingredients": ["salmon", "broccoli", "sweet potato"],
                    "all_ingredients": ["salmon fillets", "broccoli", "sweet potato", "olive oil", "lemon", "herbs"],
                    "time": 25, "calories": 420, "tags": ["omega-3", "one-pan"]
                },
                {
                    "title": "Grilled Chicken with Quinoa",
                    "main_ingredients": ["chicken breast", "quinoa", "green beans"],
                    "all_ingredients": ["chicken breast", "quinoa", "green beans", "garlic", "olive oil", "lemon"],
                    "time": 20, "calories": 380, "tags": ["lean-protein", "complete"]
                },
                {
                    "title": "Turkey Meatballs with Zucchini Noodles",
                    "main_ingredients": ["ground turkey", "zucchini", "marinara"],
                    "all_ingredients": ["lean ground turkey", "zucchini", "marinara sauce", "garlic", "italian herbs"],
                    "time": 25, "calories": 320, "tags": ["low-carb", "lean"]
                },
                {
                    "title": "Sheet Pan Chicken Fajitas",
                    "main_ingredients": ["chicken strips", "bell peppers", "onions"],
                    "all_ingredients": ["chicken breast strips", "bell peppers", "onions", "fajita seasoning", "olive oil"],
                    "time": 20, "calories": 320, "tags": ["one-pan", "colorful"]
                }
            ],
            
            "weekend_breakfast": [
                {
                    "title": "Buttermilk Pancakes with Turkey Sausage",
                    "main_ingredients": ["flour", "buttermilk", "turkey sausage"],
                    "all_ingredients": ["flour", "buttermilk", "eggs", "butter", "turkey sausage", "syrup"],
                    "time": 25, "calories": 480, "tags": ["comfort", "weekend-special"]
                },
                {
                    "title": "Chicken and Waffles (Light)",
                    "main_ingredients": ["chicken tenders", "waffle mix"],
                    "all_ingredients": ["chicken tenderloins", "waffle mix", "honey", "hot sauce"],
                    "time": 40, "calories": 520, "tags": ["soul-food", "special"]
                },
                {
                    "title": "Southern Breakfast Hash",
                    "main_ingredients": ["potatoes", "turkey sausage", "eggs"],
                    "all_ingredients": ["diced potatoes", "turkey sausage", "eggs", "bell peppers", "onions"],
                    "time": 30, "calories": 450, "tags": ["hearty", "one-pan"]
                }
            ],
            
            "weekend_dinner": [
                {
                    "title": "Southern Fried Chicken with Mac and Cheese",
                    "main_ingredients": ["chicken pieces", "pasta", "cheese"],
                    "all_ingredients": ["chicken pieces", "flour", "buttermilk", "elbow pasta", "cheddar cheese"],
                    "time": 60, "calories": 720, "tags": ["soul-food", "comfort"]
                },
                {
                    "title": "BBQ Ribs with Collard Greens",
                    "main_ingredients": ["pork ribs", "collard greens"],
                    "all_ingredients": ["pork ribs", "bbq sauce", "collard greens", "smoked turkey", "onions"],
                    "time": 180, "calories": 650, "tags": ["soul-food", "slow-cooked"]
                },
                {
                    "title": "Shrimp and Grits",
                    "main_ingredients": ["shrimp", "grits", "bacon"],
                    "all_ingredients": ["shrimp", "stone-ground grits", "bacon", "bell peppers", "onions"],
                    "time": 35, "calories": 460, "tags": ["lowcountry", "seafood"]
                }
            ]
        }
    def get_current_season(self) -> str:
        """Determine current season"""
        month = datetime.now().month
        if month in [12, 1, 2]:
            return "winter"
        elif month in [3, 4, 5]:
            return "spring"
        elif month in [6, 7, 8]:
            return "summer"
        else:
            return "fall"
    
    def score_recipe(self, recipe: Dict, sale_items: List[Dict] = None, user_history: List[str] = None) -> float:
        """Calculate recommendation score for a recipe"""
        score = recipe.get("rating", 4.5)
        
        if sale_items:
            for ingredient in recipe["main_ingredients"]:
                for sale_item in sale_items:
                    if ingredient.lower() in sale_item["name"].lower():
                        score += 1.0
                        break
        
        if recipe["time"] <= 30:
            score += 0.5
        
        for tag in recipe.get("tags", []):
            if tag in ["healthy", "high-protein", "quick"]:
                score += 0.3
        
        if user_history and recipe["title"] in user_history[-7:]:
            score -= 0.5
        
        return round(score, 2)
    
    def get_smart_recommendations(self, meal_type: str, day_type: str, count: int = 5) -> List[Dict]:
        """Get top recipe recommendations for a meal type"""
        if day_type == "weekend":
            if meal_type == "breakfast":
                recipes = self.expanded_recipes["weekend_breakfast"]
            elif meal_type == "dinner":
                recipes = self.expanded_recipes["weekend_dinner"]
            else:
                recipes = self.expanded_recipes["weekday_lunch"]
        else:
            if meal_type == "breakfast":
                recipes = self.expanded_recipes["weekday_breakfast"]
            elif meal_type == "lunch":
                recipes = self.expanded_recipes["weekday_lunch"]
            else:
                recipes = self.expanded_recipes["weekday_dinner"]
        
        filtered_recipes = []
        
        for recipe in recipes:
            if self.prefs.recipe_contains_dislikes(recipe):
                continue
            
            if self.prefs.recipe_is_banned(recipe):
                continue
            
            if self.prefs.was_served_recently(recipe, weeks_back=2):
                continue
            
            filtered_recipes.append(recipe)
        
        if len(filtered_recipes) < count:
            for recipe in recipes:
                if (not self.prefs.recipe_contains_dislikes(recipe) and 
                    not self.prefs.recipe_is_banned(recipe) and 
                    not self.prefs.was_served_recently(recipe, weeks_back=1)):
                    
                    if recipe not in filtered_recipes:
                        filtered_recipes.append(recipe)
        
        favorites = [r for r in filtered_recipes if r["title"] in self.prefs.preferences["family_favorites"]]
        non_favorites = [r for r in filtered_recipes if r["title"] not in self.prefs.preferences["family_favorites"]]
        
        random.shuffle(favorites)
        random.shuffle(non_favorites)
        
        result = []
        result.extend(favorites[:max(1, count//3)])
        
        for recipe in non_favorites:
            if len(result) >= count:
                break
            if recipe not in result:
                result.append(recipe)
        
        return result[:count]
    
    def get_recipes_by_day_type(self, day_type: str, meal: str) -> list:
        """Get recipes based on day type and meal"""
        if day_type == "weekend":
            if meal == "breakfast":
                return self.expanded_recipes["weekend_breakfast"]
            elif meal == "dinner":
                return self.expanded_recipes["weekend_dinner"]
            else:
                return self.expanded_recipes["weekday_lunch"]
        else:
            if meal == "breakfast":
                return self.expanded_recipes["weekday_breakfast"] 
            elif meal == "lunch":
                return self.expanded_recipes["weekday_lunch"]
            elif meal == "dinner":
                return self.expanded_recipes["weekday_dinner"]
        return []
    
class SaleBasedRecommendationEngine:
    """Enhanced recommendation engine that prioritizes sale items"""
    
    def __init__(self, preferences_manager, meal_rotator):
        self.prefs = preferences_manager
        self.rotator = meal_rotator
        
    def get_sale_ingredient_matches(self, sale_items: list) -> dict:
        """Map sale items to recipe ingredients"""
        sale_matches = {
            "proteins": [],
            "vegetables": [], 
            "pantry": []
        }
        
        for item in sale_items:
            name = item['name'].lower()
            
            if any(protein in name for protein in ['chicken', 'turkey', 'salmon', 'ground turkey', 'beef', 'pork', 'fish']):
                sale_matches["proteins"].append({
                    "ingredient": self._extract_protein_type(name),
                    "sale_info": item
                })
            
            elif any(veg in name for veg in ['broccoli', 'spinach', 'bell pepper', 'sweet potato', 'asparagus', 'green beans']):
                sale_matches["vegetables"].append({
                    "ingredient": self._extract_vegetable_type(name),
                    "sale_info": item
                })
            
            elif any(pantry in name for pantry in ['rice', 'quinoa', 'pasta', 'beans', 'cheese']):
                sale_matches["pantry"].append({
                    "ingredient": self._extract_pantry_type(name),
                    "sale_info": item
                })
        
        return sale_matches
    
    def _extract_protein_type(self, item_name: str) -> str:
        """Extract the type of protein from sale item name"""
        if 'chicken breast' in item_name or 'chicken' in item_name:
            return 'chicken breast'
        elif 'ground turkey' in item_name:
            return 'ground turkey'
        elif 'salmon' in item_name:
            return 'salmon'
        elif 'turkey' in item_name:
            return 'turkey'
        elif 'beef' in item_name:
            return 'ground beef'
        elif 'pork' in item_name:
            return 'pork'
        return 'protein'
    
    def _extract_vegetable_type(self, item_name: str) -> str:
        """Extract vegetable type from sale item name"""
        veg_map = {
            'broccoli': 'broccoli',
            'spinach': 'spinach', 
            'bell pepper': 'bell pepper',
            'sweet potato': 'sweet potato',
            'asparagus': 'asparagus',
            'green beans': 'green beans',
            'carrots': 'carrots',
            'onion': 'onion'
        }
        
        for veg, standard_name in veg_map.items():
            if veg in item_name:
                return standard_name
        return 'vegetables'
    
    def _extract_pantry_type(self, item_name: str) -> str:
        """Extract pantry item type"""
        if 'rice' in item_name:
            return 'rice'
        elif 'quinoa' in item_name:
            return 'quinoa'
        elif 'cheese' in item_name:
            return 'cheese'
        elif 'pasta' in item_name:
            return 'pasta'
        elif 'beans' in item_name:
            return 'beans'
        return 'pantry item'
    
    def get_sale_based_recommendations(self, sale_items: list, meal_type: str, day_type: str, count: int = 5) -> list:
        """Get recommendations prioritizing sale items"""
        
        sale_matches = self.get_sale_ingredient_matches(sale_items)
        all_recipes = self.rotator.get_smart_recommendations(meal_type, day_type, count * 2)
        
        scored_recipes = []
        
        for recipe in all_recipes:
            score = 0
            sale_benefits = []
            
            recipe_ingredients = [ing.lower() for ing in recipe.get('all_ingredients', [])]
            
            for protein_match in sale_matches["proteins"]:
                if any(protein_match["ingredient"].lower() in ing for ing in recipe_ingredients):
                    score += 10
                    sale_benefits.append({
                        "type": "protein",
                        "ingredient": protein_match["ingredient"],
                        "savings": protein_match["sale_info"]["savings"],
                        "discount": protein_match["sale_info"]["discount_percentage"]
                    })
            
            for veg_match in sale_matches["vegetables"]:
                if any(veg_match["ingredient"].lower() in ing for ing in recipe_ingredients):
                    score += 5
                    sale_benefits.append({
                        "type": "vegetable", 
                        "ingredient": veg_match["ingredient"],
                        "savings": veg_match["sale_info"]["savings"],
                        "discount": veg_match["sale_info"]["discount_percentage"]
                    })
            
            for pantry_match in sale_matches["pantry"]:
                if any(pantry_match["ingredient"].lower() in ing for ing in recipe_ingredients):
                    score += 3
                    sale_benefits.append({
                        "type": "pantry",
                        "ingredient": pantry_match["ingredient"], 
                        "savings": pantry_match["sale_info"]["savings"],
                        "discount": pantry_match["sale_info"]["discount_percentage"]
                    })
            
            recipe_copy = recipe.copy()
            recipe_copy["sale_score"] = score
            recipe_copy["sale_benefits"] = sale_benefits
            recipe_copy["total_sale_savings"] = sum(benefit["savings"] for benefit in sale_benefits)
            
            scored_recipes.append(recipe_copy)
        
        scored_recipes.sort(key=lambda x: (x["sale_score"], x["total_sale_savings"]), reverse=True)
        
        return scored_recipes[:count]
class MealPrepScheduler:
    """Meal prep scheduler with time estimation and task organization"""
    
    def __init__(self):
        self.prep_tasks = {
            "proteins": {
                "time_minutes": 30, 
                "keeps_days": 3,
                "examples": ["Cook chicken breast", "Brown ground turkey", "Season salmon"]
            },
            "vegetables": {
                "time_minutes": 20, 
                "keeps_days": 4,
                "examples": ["Chop bell peppers", "Steam broccoli", "Roast sweet potatoes"]
            }, 
            "grains": {
                "time_minutes": 25, 
                "keeps_days": 5,
                "examples": ["Cook quinoa", "Prepare brown rice", "Cook pasta"]
            },
            "sauces_dressings": {
                "time_minutes": 15, 
                "keeps_days": 7,
                "examples": ["Make marinara", "Prep salad dressing", "Mix seasonings"]
            }
        }
        
        self.weekly_prep_plan = {
            "sunday_prep": [],
            "mid_week_prep": [],
            "daily_tasks": {},
            "total_prep_time": 0
        }
    
    def categorize_ingredient(self, ingredient: str) -> str:
        """Categorize an ingredient for prep planning"""
        ingredient_lower = ingredient.lower()
        
        if any(protein in ingredient_lower for protein in ['chicken', 'turkey', 'salmon', 'beef', 'pork', 'fish', 'eggs']):
            return "proteins"
        
        elif any(veg in ingredient_lower for veg in ['broccoli', 'spinach', 'bell pepper', 'sweet potato', 'asparagus', 'carrots', 'onion', 'lettuce']):
            return "vegetables"
        
        elif any(grain in ingredient_lower for grain in ['rice', 'quinoa', 'pasta', 'bread', 'potato']):
            return "grains"
        
        elif any(sauce in ingredient_lower for sauce in ['sauce', 'dressing', 'marinade', 'seasoning']):
            return "sauces_dressings"
        
        else:
            return "other"
    
    def analyze_week_schedule(self, week_meal_plan: dict) -> dict:
        """Analyze the week's meal plan and suggest prep schedule"""
        
        prep_plan = {
            "sunday_prep": [],
            "mid_week_prep": [],
            "daily_tasks": {},
            "total_prep_time": 0,
            "ingredients_by_category": {
                "proteins": [],
                "vegetables": [], 
                "grains": [],
                "sauces_dressings": [],
                "other": []
            }
        }
        
        all_ingredients = []
        late_night_days = []
        
        for day_key, day_info in week_meal_plan.items():
            day_name = day_info.get("day_name", "Unknown")
            
            if day_info.get("late_night", False):
                late_night_days.append(day_name)
                prep_plan["daily_tasks"][day_name] = {
                    "morning": ["Set up slow cooker or prep Instant Pot meal"],
                    "evening": ["Meal ready when you arrive home"],
                    "prep_type": "late_night"
                }
            
            for meal_type in ["breakfast", "lunch", "dinner"]:
                meal = day_info.get(meal_type, "")
                if meal:
                    ingredients = self._get_basic_ingredients_for_meal(meal)
                    all_ingredients.extend(ingredients)
        
        for ingredient in set(all_ingredients):
            category = self.categorize_ingredient(ingredient)
            if category != "other":
                prep_plan["ingredients_by_category"][category].append(ingredient)
        
        return prep_plan
    
    def _get_basic_ingredients_for_meal(self, meal_name: str) -> list:
        """Get basic ingredients for a meal"""
        meal_lower = meal_name.lower()
        
        if "chicken" in meal_lower:
            return ["chicken breast", "olive oil", "seasonings", "vegetables"]
        elif "salmon" in meal_lower:
            return ["salmon", "lemon", "asparagus", "olive oil"]
        elif "turkey" in meal_lower and "meatball" in meal_lower:
            return ["ground turkey", "marinara sauce", "pasta", "herbs"]
        elif "quinoa" in meal_lower:
            return ["quinoa", "vegetables", "dressing"]
        elif "scramble" in meal_lower:
            return ["eggs", "turkey sausage", "bell pepper", "spinach"]
        else:
            return ["protein", "vegetables", "seasonings"]
    
    def create_prep_schedule(self, prep_plan: dict) -> dict:
        """Create a detailed prep schedule with timing"""
        
        schedule = prep_plan.copy()
        
        sunday_tasks = []
        total_sunday_time = 0
        
        if prep_plan["ingredients_by_category"]["proteins"]:
            proteins = prep_plan["ingredients_by_category"]["proteins"]
            task_time = self.prep_tasks["proteins"]["time_minutes"]
            sunday_tasks.append({
                "category": "proteins",
                "task": f"Prep proteins: {', '.join(proteins[:3])}",
                "time_minutes": task_time,
                "keeps_until": "Wednesday"
            })
            total_sunday_time += task_time
        
        if prep_plan["ingredients_by_category"]["grains"]:
            grains = prep_plan["ingredients_by_category"]["grains"]
            task_time = self.prep_tasks["grains"]["time_minutes"]
            sunday_tasks.append({
                "category": "grains",
                "task": f"Cook grains: {', '.join(grains[:2])}",
                "time_minutes": task_time,
                "keeps_until": "Friday"
            })
            total_sunday_time += task_time
        
        if prep_plan["ingredients_by_category"]["vegetables"]:
            vegetables = prep_plan["ingredients_by_category"]["vegetables"]
            veg_task_time = self.prep_tasks["vegetables"]["time_minutes"]
            
            sunday_veggies = vegetables[:len(vegetables)//2]
            midweek_veggies = vegetables[len(vegetables)//2:]
            
            if sunday_veggies:
                sunday_tasks.append({
                    "category": "vegetables",
                    "task": f"Prep vegetables: {', '.join(sunday_veggies)}",
                    "time_minutes": veg_task_time // 2,
                    "keeps_until": "Wednesday"
                })
                total_sunday_time += veg_task_time // 2
            
            if midweek_veggies:
                schedule["mid_week_prep"].append({
                    "category": "vegetables",
                    "task": f"Fresh vegetables: {', '.join(midweek_veggies)}",
                    "time_minutes": veg_task_time // 2,
                    "day": "Wednesday",
                    "keeps_until": "Saturday"
                })
        
        schedule["sunday_prep"] = sunday_tasks
        schedule["total_prep_time"] = total_sunday_time + sum(
            task["time_minutes"] for task in schedule["mid_week_prep"]
        )
        
        return schedule
class CalendarIntegrator:
    """Handle calendar integration and busy day detection"""
    
    def __init__(self):
        self.calendar_events = {}
        self.busy_day_threshold = 6
        
    def add_mock_events(self, date_str: str, events: list):
        """Add mock calendar events for testing"""
        self.calendar_events[date_str] = events
    
    def is_busy_day(self, date_str: str) -> dict:
        """Determine if a day is busy based on calendar events"""
        events = self.calendar_events.get(date_str, [])
        
        total_busy_hours = 0
        event_count = len(events)
        
        for event in events:
            duration = event.get("duration_hours", 1)
            total_busy_hours += duration
        
        is_busy = total_busy_hours >= self.busy_day_threshold or event_count >= 4
        
        return {
            "is_busy": is_busy,
            "total_hours": total_busy_hours,
            "event_count": event_count,
            "events": events,
            "recommendation": self._get_meal_recommendation(is_busy, total_busy_hours)
        }
    
    def _get_meal_recommendation(self, is_busy: bool, busy_hours: float) -> dict:
        """Get meal recommendations based on how busy the day is"""
        if busy_hours >= 8:
            return {
                "meal_style": "late_night_ready",
                "prep_style": "slow_cooker_or_instant_pot",
                "message": "Very busy day - use slow cooker or Instant Pot",
                "prep_time": "Set up in morning (10 min max)"
            }
        elif busy_hours >= 6:
            return {
                "meal_style": "quick_and_easy", 
                "prep_style": "minimal_prep",
                "message": "Busy day - keep meals simple and quick",
                "prep_time": "20 minutes or less"
            }
        elif busy_hours >= 4:
            return {
                "meal_style": "normal_with_prep",
                "prep_style": "some_prep_ok",
                "message": "Moderate schedule - normal meals with some prep OK",
                "prep_time": "30-45 minutes OK"
            }
        else:
            return {
                "meal_style": "any_style",
                "prep_style": "full_cooking_ok", 
                "message": "Light schedule - perfect day for cooking projects!",
                "prep_time": "Any cooking time fine"
            }
    
    def analyze_weekly_schedule(self, week_meal_plan: dict) -> dict:
        """Analyze the entire week's schedule and suggest optimal meal planning"""
        
        weekly_analysis = {
            "busy_days": [],
            "light_days": [],
            "best_prep_days": [],
            "late_night_needed": [],
            "cooking_project_days": [],
            "weekly_recommendations": {}
        }
        
        for day_key, day_info in week_meal_plan.items():
            date_str = day_info.get("date", "")
            day_name = day_info.get("day_name", "")
            
            day_analysis = self.is_busy_day(date_str)
            
            if day_analysis["is_busy"]:
                weekly_analysis["busy_days"].append({
                    "day": day_name,
                    "date": date_str,
                    "busy_hours": day_analysis["total_hours"],
                    "recommendation": day_analysis["recommendation"]
                })
                
                if day_analysis["total_hours"] >= 8:
                    weekly_analysis["late_night_needed"].append(day_name)
            
            else:
                weekly_analysis["light_days"].append({
                    "day": day_name,
                    "date": date_str,
                    "busy_hours": day_analysis["total_hours"],
                    "recommendation": day_analysis["recommendation"]
                })
                
                if day_name in ["Sunday", "Saturday"]:
                    weekly_analysis["best_prep_days"].append(day_name)
                elif day_analysis["total_hours"] < 2:
                    weekly_analysis["cooking_project_days"].append(day_name)
        
        weekly_analysis["weekly_recommendations"] = self._generate_weekly_recommendations(weekly_analysis)
        
        return weekly_analysis
    
    def _generate_weekly_recommendations(self, analysis: dict) -> dict:
        """Generate smart recommendations for the entire week"""
        recommendations = {
            "meal_prep_strategy": "",
            "shopping_strategy": "",
            "cooking_strategy": "",
            "specific_suggestions": []
        }
        
        busy_day_count = len(analysis["busy_days"])
        light_day_count = len(analysis["light_days"])
        
        if busy_day_count >= 4:
            recommendations["meal_prep_strategy"] = "Heavy prep recommended - prep 3-4 meals on Sunday"
            recommendations["specific_suggestions"].append("Sunday: 2-3 hours of meal prep")
            recommendations["specific_suggestions"].append("Focus on slow cooker and one-pot meals")
        elif busy_day_count >= 2:
            recommendations["meal_prep_strategy"] = "Moderate prep - focus on proteins and grains"
            recommendations["specific_suggestions"].append("Sunday: 1-2 hours protein and grain prep")
        else:
            recommendations["meal_prep_strategy"] = "Minimal prep needed - cook fresh most days"
            recommendations["specific_suggestions"].append("Light prep - just wash and chop vegetables")
        
        if analysis["late_night_needed"]:
            recommendations["shopping_strategy"] = "Buy slow cooker/Instant Pot ingredients"
            recommendations["specific_suggestions"].append(f"Late night meals needed: {', '.join(analysis['late_night_needed'])}")
        
        if analysis["cooking_project_days"]:
            recommendations["cooking_strategy"] = f"Perfect days for cooking projects: {', '.join(analysis['cooking_project_days'])}"
            recommendations["specific_suggestions"].append("Try new recipes or make-ahead meals on light days")
        
        return recommendations
def add_recipe_feedback_buttons(recipe: dict, key_suffix: str = ""):
    """Add feedback buttons to recipes"""
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        if st.button("⭐ Favorite", key=f"fav_{recipe['title']}_{key_suffix}"):
            st.session_state.family_prefs.add_favorite(recipe['title'])
            st.success("⭐ Added to favorites!")
            st.rerun()
    
    with col2:
        if st.button("❌ Dislike", key=f"dislike_{recipe['title']}_{key_suffix}"):
            st.session_state[f"show_ingredient_dislike_{recipe['title']}"] = True
    
    with col3:
        if st.button("🚫 Never Again", key=f"ban_{recipe['title']}_{key_suffix}"):
            st.session_state.family_prefs.ban_recipe(recipe['title'])
            st.error("🚫 Recipe banned from future suggestions")
            st.rerun()
    
    with col4:
        if st.button("✅ We Made This", key=f"made_{recipe['title']}_{key_suffix}"):
            today = datetime.now().strftime("%Y-%m-%d")
            st.session_state.family_prefs.log_meal(recipe['title'], today)
            st.success("✅ Logged in meal history!")
            st.rerun()
    
    if st.session_state.get(f"show_ingredient_dislike_{recipe['title']}", False):
        st.write("**Which ingredient didn't you like?**")
        selected_ingredient = st.selectbox(
            "Select ingredient to dislike:",
            recipe.get("all_ingredients", []),
            key=f"ingredient_select_{recipe['title']}_{key_suffix}"
        )
        
        col_a, col_b = st.columns(2)
        with col_a:
            if st.button("Add to Dislikes", key=f"confirm_dislike_{recipe['title']}_{key_suffix}"):
                st.session_state.family_prefs.add_dislike(selected_ingredient)
                st.session_state[f"show_ingredient_dislike_{recipe['title']}"] = False
                st.success(f"❌ Added '{selected_ingredient}' to dislikes")
                st.rerun()
        
        with col_b:
            if st.button("Cancel", key=f"cancel_dislike_{recipe['title']}_{key_suffix}"):
                st.session_state[f"show_ingredient_dislike_{recipe['title']}"] = False
                st.rerun()

def create_preference_ui():
    """Create UI for managing family preferences"""
    
    st.subheader("👥 Family Food Preferences")
    
    pref_tabs = st.tabs(["❌ Dislikes", "❤️ Loves", "🚫 Never Again", "⭐ Favorites"])
    
    with pref_tabs[0]:
        st.write("**Ingredients we don't like:**")
        
        col1, col2 = st.columns([3, 1])
        with col1:
            new_dislike = st.text_input("Add ingredient to dislike list:", 
                                      placeholder="e.g., mushrooms, cilantro, fish...")
        with col2:
            if st.button("Add Dislike"):
                if new_dislike:
                    st.session_state.family_prefs.add_dislike(new_dislike)
                    st.success(f"✅ Added '{new_dislike}' to dislikes")
                    st.rerun()
        
        if st.session_state.family_prefs.preferences["disliked_ingredients"]:
            st.write("**Current dislikes:**")
            for i, ingredient in enumerate(st.session_state.family_prefs.preferences["disliked_ingredients"]):
                col1, col2 = st.columns([4, 1])
                with col1:
                    st.write(f"• {ingredient}")
                with col2:
                    if st.button("Remove", key=f"remove_dislike_{i}"):
                        st.session_state.family_prefs.preferences["disliked_ingredients"].remove(ingredient)
                        st.rerun()
    
    with pref_tabs[1]:
        st.write("**Ingredients we love:**")
        
        col1, col2 = st.columns([3, 1])
        with col1:
            new_love = st.text_input("Add ingredient to love list:", 
                                   placeholder="e.g., chicken, cheese, avocado...")
        with col2:
            if st.button("Add Love"):
                if new_love:
                    st.session_state.family_prefs.add_love(new_love)
                    st.success(f"❤️ Added '{new_love}' to loves")
                    st.rerun()
        
        if st.session_state.family_prefs.preferences["loved_ingredients"]:
            st.write("**We love these:**")
            for ingredient in st.session_state.family_prefs.preferences["loved_ingredients"]:
                st.write(f"❤️ {ingredient}")
    
    with pref_tabs[2]:
        st.write("**Recipes to never suggest again:**")
        
        if st.session_state.family_prefs.preferences["never_suggest_again"]:
            for recipe in st.session_state.family_prefs.preferences["never_suggest_again"]:
                col1, col2 = st.columns([4, 1])
                with col1:
                    st.write(f"🚫 {recipe}")
                with col2:
                    if st.button("Unban", key=f"unban_{recipe}"):
                        st.session_state.family_prefs.preferences["never_suggest_again"].remove(recipe)
                        st.rerun()
        else:
            st.info("No banned recipes yet.")
    
    with pref_tabs[3]:
        st.write("**Family favorite recipes:**")
        
        if st.session_state.family_prefs.preferences["family_favorites"]:
            for recipe in st.session_state.family_prefs.preferences["family_favorites"]:
                st.write(f"⭐ {recipe}")
        else:
            st.info("No favorites marked yet. Use the ⭐ button on recipes to add them!")

def create_meal_prep_ui():
    """Create the meal prep scheduling interface"""
    
    if 'meal_prep_scheduler' not in st.session_state:
        st.session_state.meal_prep_scheduler = MealPrepScheduler()
    
    if 'calendar_integrator' not in st.session_state:
        st.session_state.calendar_integrator = CalendarIntegrator()
        today = datetime.now()
        for i in range(7):
            date_str = (today + timedelta(days=i)).strftime('%Y-%m-%d')
            day_name = (today + timedelta(days=i)).strftime('%A')
            
            if day_name in ['Monday', 'Wednesday', 'Friday']:
                st.session_state.calendar_integrator.add_mock_events(date_str, [
                    {"name": "Work meetings", "duration_hours": 6},
                    {"name": "Commute", "duration_hours": 1.5}
                ])
            elif day_name == 'Tuesday':
                st.session_state.calendar_integrator.add_mock_events(date_str, [
                    {"name": "Work", "duration_hours": 8},
                    {"name": "Evening event", "duration_hours": 2}
                ])
    
    st.header("📅 Smart Meal Prep Scheduler")
    
    if st.button("🔍 Analyze This Week's Schedule", use_container_width=True):
        with st.spinner("🧠 Analyzing your week and creating prep plan..."):
            weekly_analysis = st.session_state.calendar_integrator.analyze_weekly_schedule(st.session_state.meal_plan)
            meal_prep_plan = st.session_state.meal_prep_scheduler.analyze_week_schedule(st.session_state.meal_plan)
            full_schedule = st.session_state.meal_prep_scheduler.create_prep_schedule(meal_prep_plan)
            
            st.session_state.weekly_analysis = weekly_analysis
            st.session_state.prep_schedule = full_schedule
            
        st.success("✅ Analysis complete! Check the sections below.")
    
    if 'weekly_analysis' in st.session_state and 'prep_schedule' in st.session_state:
        
        st.subheader("📊 This Week's Schedule Overview")
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            busy_days = len(st.session_state.weekly_analysis["busy_days"])
            st.metric("Busy Days", busy_days)
        
        with col2:
            light_days = len(st.session_state.weekly_analysis["light_days"])
            st.metric("Light Days", light_days)
        
        with col3:
            prep_time = st.session_state.prep_schedule["total_prep_time"]
            st.metric("Total Prep Time", f"{prep_time} min")
        
        with col4:
            late_night_days = len(st.session_state.weekly_analysis["late_night_needed"])
            st.metric("Late Night Meals", late_night_days)
        
        st.subheader("💡 Smart Recommendations for This Week")
        
        recommendations = st.session_state.weekly_analysis["weekly_recommendations"]
        
        st.write(f"**🎯 Meal Prep Strategy:** {recommendations['meal_prep_strategy']}")
        
        if recommendations["shopping_strategy"]:
            st.write(f"**🛒 Shopping Focus:** {recommendations['shopping_strategy']}")
        
        if recommendations["cooking_strategy"]:
            st.write(f"**👨‍🍳 Cooking Strategy:** {recommendations['cooking_strategy']}")
        
        if recommendations["specific_suggestions"]:
            st.write("**📝 Specific Suggestions:**")
            for suggestion in recommendations["specific_suggestions"]:
                st.write(f"• {suggestion}")
if 'meal_plan' not in st.session_state or 'last_update_date' not in st.session_state:
    st.session_state.last_update_date = datetime.now().date()
    st.session_state.meal_plan = {}
    for i in range(7):
        day_name = (datetime.now() + timedelta(days=i)).strftime("%A")
        is_weekend = day_name in ["Saturday", "Sunday"]
        st.session_state.meal_plan[f"day_{i}"] = {
            "date": (datetime.now() + timedelta(days=i)).strftime("%Y-%m-%d"),
            "day_name": day_name,
            "is_weekend": is_weekend,
            "breakfast": "",
            "lunch": "",
            "dinner": "",
            "late_night": False,
            "prep_needed": False
        }

# Check if we need to update dates (new day)
elif datetime.now().date() != st.session_state.last_update_date:
    st.session_state.last_update_date = datetime.now().date()
    
    # Update all dates but keep the meal data
    for i in range(7):
        day_name = (datetime.now() + timedelta(days=i)).strftime("%A")
        is_weekend = day_name in ["Saturday", "Sunday"]
        
        # Update dates but preserve existing meals
        existing_breakfast = st.session_state.meal_plan[f"day_{i}"].get("breakfast", "")
        existing_lunch = st.session_state.meal_plan[f"day_{i}"].get("lunch", "")
        existing_dinner = st.session_state.meal_plan[f"day_{i}"].get("dinner", "")
        existing_late_night = st.session_state.meal_plan[f"day_{i}"].get("late_night", False)
        
        st.session_state.meal_plan[f"day_{i}"] = {
            "date": (datetime.now() + timedelta(days=i)).strftime("%Y-%m-%d"),
            "day_name": day_name,
            "is_weekend": is_weekend,
            "breakfast": existing_breakfast,
            "lunch": existing_lunch,
            "dinner": existing_dinner,
            "late_night": existing_late_night,
            "prep_needed": False
        }

if 'grocery_list' not in st.session_state:
    st.session_state.grocery_list = []

if 'kroger_store' not in st.session_state:
    st.session_state.kroger_store = find_kroger_store(ZIP_CODE)

if 'family_prefs' not in st.session_state:
    st.session_state.family_prefs = FamilyPreferencesManager()

if 'meal_rotator' not in st.session_state:
    st.session_state.meal_rotator = SmartMealRotator(st.session_state.family_prefs)

if 'sale_based_engine' not in st.session_state:
    st.session_state.sale_based_engine = SaleBasedRecommendationEngine(
        st.session_state.family_prefs, 
        st.session_state.meal_rotator
    )

if 'purchase_analyzer' not in st.session_state:
    st.session_state.purchase_analyzer = PurchaseTimingAnalyzer()
    
st.title("🍽️ Smart Family Meal Planner")
st.subheader("Soul food weekends • Healthy weekdays • Smart savings • Meal prep scheduling")

# Temporary debug/fix button
if st.button("🔄 Force Date Update", key="force_date_update"):
    # Clear the meal plan to force regeneration
    if 'meal_plan' in st.session_state:
        del st.session_state.meal_plan
    if 'last_update_date' in st.session_state:
        del st.session_state.last_update_date
    st.success("✅ Session cleared! Refresh the page to see updated dates.")
    st.rerun()

# Store connection info
if st.session_state.kroger_store:
    store = st.session_state.kroger_store
    st.success(f"📍 {store['name']} - {store['address']['city']}, {store['address']['state']}")

tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
    "📅 Weekly Plan", 
    "📊 Sales & Savings", 
    "🍳 Smart Recipes", 
    "📋 Meal Prep", 
    "🛒 Grocery List", 
    "⚙️ Settings"
])

with tab1:
    st.header("📅 This Week's Meal Plan")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if st.button("🚀 Smart Fill Week", use_container_width=True):
            sale_items = st.session_state.get('sale_items', [])
            
            for day_key, day_info in st.session_state.meal_plan.items():
                day_type = "weekend" if day_info["is_weekend"] else "weekday"
                
                for meal_type in ["breakfast", "lunch", "dinner"]:
                    if not day_info[meal_type]:
                        if sale_items:
                            recommendations = st.session_state.sale_based_engine.get_sale_based_recommendations(
                                sale_items, meal_type, day_type, 1
                            )
                        else:
                            recommendations = st.session_state.meal_rotator.get_smart_recommendations(
                                meal_type, day_type, 1
                            )
                        
                        if recommendations:
                            day_info[meal_type] = recommendations[0]['title']
            
            st.success("✅ Week filled with smart, money-saving recommendations!")
            st.rerun()
    
    with col2:
        if st.button("🔄 Clear All", use_container_width=True, key="clear_meal_plan"):
            for day_info in st.session_state.meal_plan.values():
                day_info.update({"breakfast": "", "lunch": "", "dinner": ""})
            st.success("✅ Meal plan cleared!")
            st.rerun()
    
    with col3:
        if st.button("📋 Generate Grocery List", use_container_width=True):
            new_items = []
            for day_info in st.session_state.meal_plan.values():
                # NEW: Skip days when dining out or traveling
                if day_info.get("dining_out", False) or day_info.get("out_of_town", False):
                    continue
                    
                for meal in [day_info["breakfast"], day_info["lunch"], day_info["dinner"]]:
                    if meal:
                        if "chicken" in meal.lower():
                            new_items.extend(["chicken breast", "seasonings", "olive oil"])
                        elif "salmon" in meal.lower():
                            new_items.extend(["salmon fillets", "vegetables", "lemon"])
                        elif "turkey" in meal.lower():
                            new_items.extend(["ground turkey", "herbs", "vegetables"])
            
            for item in set(new_items):
                if item not in st.session_state.grocery_list:
                    st.session_state.grocery_list.append(item)
            
            # Enhanced success message
            excluded_days = sum(1 for day in st.session_state.meal_plan.values() 
                              if day.get("dining_out", False) or day.get("out_of_town", False))
            if excluded_days > 0:
                st.success(f"✅ Added {len(set(new_items))} items to grocery list! (Skipped {excluded_days} dining out/travel days)")
            else:
                st.success(f"✅ Added {len(set(new_items))} items to grocery list!")
    
    st.subheader("📊 Weekly Overview")
    
    cols = st.columns(7)
    
    for i, (day_key, day_info) in enumerate(st.session_state.meal_plan.items()):
        with cols[i]:
            if day_info["is_weekend"]:
                st.markdown(f"### 🎉 {day_info['day_name']}")
                st.caption("Soul Food Day")
            else:
                st.markdown(f"### 📅 {day_info['day_name']}")
                st.caption("Healthy Day")
            
            st.caption(datetime.strptime(day_info['date'], '%Y-%m-%d').strftime('%m/%d'))
            
            # Enhanced checkboxes - add dining out options
            day_info["late_night"] = st.checkbox(
                "🌙 Late night", 
                value=day_info.get("late_night", False),
                key=f"late_{i}",
                help="Check if you'll be home late and need food ready"
            )
            
            # NEW: Add dining out toggle
            day_info["dining_out"] = st.checkbox(
                "🍽️ Dining out", 
                value=day_info.get("dining_out", False),
                key=f"dining_{i}",
                help="Check if you're eating out or ordering in"
            )
            
            # NEW: Add out of town toggle  
            day_info["out_of_town"] = st.checkbox(
                "✈️ Out of town", 
                value=day_info.get("out_of_town", False),
                key=f"travel_{i}",
                help="Check if you're traveling and won't be home"
            )
            
            # Determine if meals should be disabled
            meals_disabled = day_info.get("dining_out", False) or day_info.get("out_of_town", False)
            
            # Meal planning with conditional disable
            for meal_type in ["breakfast", "lunch", "dinner"]:
                current_meal = day_info[meal_type]
                
                if day_info["is_weekend"] and meal_type in ["breakfast", "dinner"]:
                    placeholder = f"Soul food {meal_type}..." if not meals_disabled else "Dining out"
                elif day_info["late_night"] and meal_type == "dinner":
                    placeholder = f"Quick/prep-ahead {meal_type}..." if not meals_disabled else "Dining out"
                else:
                    placeholder = f"Healthy {meal_type}..." if not meals_disabled else "Dining out"
                
                day_info[meal_type] = st.text_input(
                    meal_type.title(),
                    value=current_meal if not meals_disabled else "",
                    key=f"{meal_type}_{i}",
                    placeholder=placeholder,
                    disabled=meals_disabled  # NEW: Disable when dining out/traveling
                )
            
            # Enhanced status indicators
            if day_info.get("out_of_town", False):
                st.info("✈️ Out of town - no meal planning needed")
            elif day_info.get("dining_out", False):
                st.info("🍽️ Dining out - no cooking needed")
            elif day_info["late_night"]:
                st.info("🌙 Late night meal prep needed")
            
            if day_info["is_weekend"]:
                st.success("🎉 Soul food day!")
with tab2:
    st.header("📊 Smart Sales Analysis & Purchase Timing")
    
    if st.button("🔄 Refresh Sales Data", use_container_width=True):
        st.cache_data.clear()
        
    with st.spinner("🔍 Finding the best deals and analyzing purchase timing..."):
        sale_items = extract_sale_items()
    
    if sale_items:
        st.success(f"Found {len(sale_items)} items on sale!")
        st.session_state.sale_items = sale_items
        
        st.subheader("🎯 Smart Purchase Recommendations")
        
        sale_items.sort(key=lambda x: x['discount_percentage'], reverse=True)
        
        for i, item in enumerate(sale_items[:8]):
            recommendation = st.session_state.purchase_analyzer.get_recommendation(item['name'], item['discount_percentage'])
            
            with st.expander(f"{recommendation['action']} - {item['name'][:50]}"):
                col1, col2, col3 = st.columns([2, 1, 1])
                
                with col1:
                    st.write(f"**Category:** {item['category']}")
                    st.write(f"**Why:** {recommendation['reason']}")
                    st.write(f"**Best Use:** {recommendation['timing']}")
                    st.write(f"**Confidence:** {recommendation['confidence']}")
                    
                    matching_recipes = st.session_state.sale_based_engine.get_sale_based_recommendations(
                        [item], "dinner", "weekday", 2
                    )
                    if matching_recipes:
                        st.write("**💡 Recipe Ideas:**")
                        for recipe in matching_recipes:
                            if recipe.get('sale_benefits'):
                                st.write(f"• {recipe['title']}")
                
                with col2:
                    st.metric("Regular Price", f"${item['regular_price']:.2f}")
                    st.metric("Sale Price", f"${item['sale_price']:.2f}")
                
                with col3:
                    st.metric("You Save", f"${item['savings']:.2f}")
                    st.metric("Discount", f"{item['discount_percentage']}%")
                
                col_a, col_b = st.columns(2)
                with col_a:
                    if st.button("🛒 Add to List", key=f"add_{i}"):
                        if item['name'] not in st.session_state.grocery_list:
                            st.session_state.grocery_list.append(item['name'])
                            st.success("✅ Added!")
                            st.rerun()
                
                with col_b:
                    if st.button("🍽️ Get Recipes", key=f"recipe_{i}"):
                        recipes = st.session_state.sale_based_engine.get_sale_based_recommendations(
                            [item], "dinner", "weekday", 3
                        )
                        if recipes:
                            st.info(f"💡 Found {len(recipes)} recipes using {item['category'].lower()} on sale!")
                            for recipe in recipes:
                                st.write(f"• {recipe['title']} (save ${recipe.get('total_sale_savings', 0):.2f})")
        
        st.subheader("📈 Sales Analysis Dashboard")
        
        if len(sale_items) > 3:
            col1, col2 = st.columns(2)
            
            with col1:
                df = pd.DataFrame(sale_items)
                fig = px.histogram(df, x="discount_percentage", 
                                 title="Discount Distribution")
                st.plotly_chart(fig, use_container_width=True)
            
            with col2:
                category_counts = df['category'].value_counts()
                fig = px.pie(values=category_counts.values, names=category_counts.index,
                           title="Sales by Category")
                st.plotly_chart(fig, use_container_width=True)
        
        weekly_analysis = st.session_state.purchase_analyzer.analyze_weekly_savings(sale_items)
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric("Total Possible Savings", f"${weekly_analysis['total_possible_savings']:.2f}")
        
        with col2:
            st.metric("High-Value Deals", weekly_analysis['high_value_count'])
        
        with col3:
            st.metric("Average Discount", f"{weekly_analysis['average_discount']:.1f}%")
        
        st.info(f"💡 {weekly_analysis['recommendation']}")
    
    else:
        st.info("No current sales found. This might be due to API limitations or no current promotions.")

with tab3:
    st.header("🍳 Smart Recipe Recommendations")
    
    st.subheader("🎯 Get Sale-Based Smart Recommendations")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        rec_day_type = st.selectbox("Day Type:", ["weekday", "weekend"], key="rec_day_type")
    
    with col2:
        rec_meal_type = st.selectbox("Meal:", ["breakfast", "lunch", "dinner"], key="rec_meal_type")
    
    with col3:
        rec_count = st.slider("Number of suggestions:", 3, 8, 5, key="rec_count")
    
    with col4:
        use_sales = st.checkbox("Prioritize sale items", value=True, help="Use current sales to influence recommendations")
    
    if st.button("🤖 Get Smart Recommendations", use_container_width=True):
        with st.spinner("🧠 Finding recipes that save money and taste great..."):
            
            if use_sales and 'sale_items' in st.session_state and st.session_state.sale_items:
                smart_recommendations = st.session_state.sale_based_engine.get_sale_based_recommendations(
                    st.session_state.sale_items, rec_meal_type, rec_day_type, rec_count
                )
                recommendation_type = "sale-based"
            else:
                smart_recommendations = st.session_state.meal_rotator.get_smart_recommendations(
                    rec_meal_type, rec_day_type, rec_count
                )
                recommendation_type = "variety-based"
            
            st.session_state.current_recommendations = smart_recommendations
            st.session_state.recommendation_type = recommendation_type
    
    if 'current_recommendations' in st.session_state and st.session_state.current_recommendations:
        
        rec_type = st.session_state.get('recommendation_type', 'variety-based')
        
        if rec_type == "sale-based":
            st.subheader("💰 Your Money-Saving Recipe Recommendations")
            st.info("✨ These recipes use ingredients currently on sale at your store!")
        else:
            st.subheader("🎉 Your Variety-Based Recommendations")
            st.info("✨ These recipes offer great variety and avoid recent repeats!")
        
        for i, recipe in enumerate(st.session_state.current_recommendations):
            title_parts = [f"🍽️ {recipe['title']} ({recipe['time']} min)"]
            
            if recipe.get('total_sale_savings', 0) > 0:
                title_parts.append(f"💰 Save ${recipe['total_sale_savings']:.2f}")
            
            with st.expander(" - ".join(title_parts)):
                col1, col2 = st.columns([3, 1])
                
                with col1:
                    st.write(f"⏱️ **Time:** {recipe['time']} minutes")
                    st.write(f"🔥 **Calories:** {recipe['calories']} per serving")
                    st.write(f"🏷️ **Tags:** {', '.join(recipe.get('tags', []))}")
                    
                    if recipe.get('sale_benefits'):
                        st.write("**💰 Sale Benefits:**")
                        for benefit in recipe['sale_benefits']:
                            st.write(f"• {benefit['ingredient']} - {benefit['discount']}% off (save ${benefit['savings']:.2f})")
                    
                    st.write("**🛒 Ingredients:**")
                    for ingredient in recipe.get("all_ingredients", []):
                        is_on_sale = False
                        if recipe.get('sale_benefits'):
                            for benefit in recipe['sale_benefits']:
                                if benefit['ingredient'].lower() in ingredient.lower():
                                    st.write(f"• 💰 {ingredient} **(ON SALE - {benefit['discount']}% off)**")
                                    is_on_sale = True
                                    break
                        
                        if not is_on_sale:
                            if any(loved.lower() in ingredient.lower() 
                                  for loved in st.session_state.family_prefs.preferences["loved_ingredients"]):
                                st.write(f"• ❤️ {ingredient}")
                            else:
                                st.write(f"• {ingredient}")
                
                with col2:
                    st.write("**📅 Quick Actions**")
                    
                    if st.button("Add to Today", key=f"today_rec_{i}"):
                        today_key = "day_0"
                        st.session_state.meal_plan[today_key][rec_meal_type] = recipe['title']
                        st.success(f"✅ Added to today's {rec_meal_type}!")
                        st.rerun()
                    
                    if st.button("+ Ingredients", key=f"ingredients_rec_{i}"):
                        added = 0
                        for ingredient in recipe.get("all_ingredients", []):
                            if ingredient not in st.session_state.grocery_list:
                                st.session_state.grocery_list.append(ingredient)
                                added += 1
                        if added > 0:
                            st.success(f"Added {added} ingredients!")
                            st.rerun()
                
                st.write("**👥 How was this recipe?**")
                add_recipe_feedback_buttons(recipe, f"rec_{i}")
with tab4:
    create_meal_prep_ui()

with tab5:
    st.header("🛒 Smart Grocery List")
    
    col1, col2, col3 = st.columns([2, 1, 1])
    
    with col1:
        new_item = st.text_input("➕ Add item to grocery list:", placeholder="Enter item name...")
    
    with col2:
        if st.button("Add Item", use_container_width=True):
            if new_item and new_item not in st.session_state.grocery_list:
                st.session_state.grocery_list.append(new_item)
                st.success("✅ Added!")
                st.rerun()
            elif new_item in st.session_state.grocery_list:
                st.warning("Already on list!")
    
    with col3:
        if st.button("🔄 Clear All", use_container_width=True, key="clear_grocery_list"):
            st.session_state.grocery_list = []
            st.success("✅ List cleared!")
            st.rerun()
    
    if st.session_state.grocery_list:
        st.subheader(f"📋 Current List ({len(st.session_state.grocery_list)} items)")
        
        categories = {
            "🥩 Proteins": ["chicken", "turkey", "salmon", "beef", "pork", "eggs"],
            "🥬 Vegetables": ["broccoli", "spinach", "lettuce", "tomato", "onion", "pepper"],
            "🥖 Pantry": ["rice", "pasta", "flour", "oil", "seasoning", "sauce"],
            "🥛 Dairy": ["milk", "cheese", "butter", "yogurt"],
            "🍎 Other": []
        }
        
        categorized_items = {cat: [] for cat in categories}
        
        for item in st.session_state.grocery_list:
            item_lower = item.lower()
            categorized = False
            
            for category, keywords in categories.items():
                if category != "🍎 Other" and any(keyword in item_lower for keyword in keywords):
                    categorized_items[category].append(item)
                    categorized = True
                    break
            
            if not categorized:
                categorized_items["🍎 Other"].append(item)
        
        for category, items in categorized_items.items():
            if items:
                st.write(f"**{category}**")
                for item in items:
                    col1, col2 = st.columns([4, 1])
                    with col1:
                        st.write(f"• {item}")
                    with col2:
                        if st.button("❌", key=f"remove_{item}"):
                            st.session_state.grocery_list.remove(item)
                            st.rerun()
        
        st.subheader("📱 Export Options")
        
        col1, col2 = st.columns(2)
        
        with col1:
            list_text = "\n".join([f"• {item}" for item in st.session_state.grocery_list])
            st.text_area("📋 Copy this list:", value=list_text, height=150)
        
        with col2:
            organized_text = ""
            for category, items in categorized_items.items():
                if items:
                    organized_text += f"\n{category}\n"
                    for item in items:
                        organized_text += f"• {item}\n"
            
            st.text_area("📂 Organized list:", value=organized_text, height=150)
    
    else:
        st.info("🛒 Your grocery list is empty. Add items above or generate from your meal plan!")
with tab6:
    st.header("⚙️ Settings & Family Preferences")
    
    settings_tabs = st.tabs(["👥 Family Preferences", "🏪 Store & Basic Settings"])
    
    with settings_tabs[0]:
        create_preference_ui()
        
        st.subheader("🌶️ Dietary Preferences")
        
        col1, col2 = st.columns(2)
        
        with col1:
            spice_level = st.selectbox("Spice tolerance:", 
                                     ["Low (mild flavors)", "Medium (some spice)", "High (bring the heat!)"],
                                     index=1)
            
            cooking_time_pref = st.selectbox("Weekday cooking time preference:",
                                           ["Under 15 minutes", "15-30 minutes", "30-45 minutes", "Don't mind longer"],
                                           index=1)
        
        with col2:
            dietary_restrictions = st.multiselect("Dietary restrictions:",
                                                ["None", "Gluten-free", "Dairy-free", "Low-sodium", 
                                                 "Heart-healthy", "Diabetic-friendly"])
            
            meal_prep_style = st.selectbox("Meal prep preference:",
                                         ["Minimal prep", "Sunday prep day", "Daily fresh cooking", "Mix of both"])
        
        if st.button("💾 Save Dietary Preferences"):
            st.session_state.family_prefs.preferences.update({
                "spice_tolerance": spice_level.split(" ")[0].lower(),
                "cooking_time_pref": cooking_time_pref,
                "dietary_restrictions": dietary_restrictions,
                "meal_prep_style": meal_prep_style
            })
            st.success("✅ Preferences saved!")
    
    with settings_tabs[1]:
        st.subheader("👨‍👩‍👧‍👦 Family Settings")
        
        col1, col2 = st.columns(2)
        
        with col1:
            family_size = st.number_input("Family Size:", min_value=1, max_value=10, value=4)
            cooking_skill = st.selectbox("Cooking Skill Level:", ["Beginner", "Intermediate", "Advanced"])
        
        with col2:
            weekend_style = st.selectbox("Weekend cooking style:", 
                                       ["Soul food classics", "Comfort food", "Mix of both"])
            budget_range = st.selectbox("Weekly grocery budget:", 
                                      ["Under $75", "$75-$100", "$100-$150", "Over $150"])
        
        st.subheader("🏪 Store Settings")
        
        if st.session_state.kroger_store:
            store = st.session_state.kroger_store
            st.success(f"✅ Connected to: {store['name']}")
            st.write(f"📍 {store['address']['addressLine1']}, {store['address']['city']}, {store['address']['state']}")
        else:
            st.warning("⚠️ No store connected")
        
        new_zip = st.text_input("Change store location (ZIP code):", value=ZIP_CODE)
        if st.button("🔄 Update Store Location"):
            st.session_state.kroger_store = find_kroger_store(new_zip)
            if st.session_state.kroger_store:
                st.success("✅ Store updated!")
                st.rerun()
            else:
                st.error("❌ Could not find store for that ZIP code")
        
        st.subheader("🍽️ Meal Planning Preferences")
        
        col1, col2 = st.columns(2)
        
        with col1:
            default_late_nights = st.multiselect("Default late night days:", 
                                               ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"])
            prep_day = st.selectbox("Meal prep day:", 
                                  ["Sunday", "Saturday", "None"])
        
        with col2:
            sale_focus = st.checkbox("Prioritize sale items in recommendations", value=True)
            variety_focus = st.checkbox("Encourage trying new recipes", value=True)
        
        if st.button("💾 Save All Settings", use_container_width=True):
            st.success("✅ Settings saved!")
            st.info("💡 Settings will be used to improve your meal recommendations")

st.markdown("---")
st.markdown("""
<div style='text-align: center; color: #666;'>
    <small>
        🔗 Connected to Kroger API • 💡 Smart recommendations based on sales & preferences<br>
        💪 Healthy weekdays • 🎉 Soul food weekends • 🌙 Late night solutions • 📅 Meal prep scheduling
    </small>
</div>
""", unsafe_allow_html=True)
