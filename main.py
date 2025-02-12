import discord
from dotenv import load_dotenv
from discord.ext import commands, tasks
import json
import os
import requests
from bs4 import BeautifulSoup

# Bot configuration
DATA_FILE = "trade_data.json"
CARD_DATA_FILE = "card_data.json"  # New file for storing scraped card data
BASE_URL = "https://pocket.limitlesstcg.com"
CARD_LIST_URL = f"{BASE_URL}/cards/"

def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r") as f:
            return json.load(f)
    return {}

def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=4)

def load_card_data():
    """Load the card data from the local file."""
    if os.path.exists(CARD_DATA_FILE):
        with open(CARD_DATA_FILE, "r") as f:
            return json.load(f)
    return []

def save_card_data(card_data):
    """Save the card data to a local file."""
    with open(CARD_DATA_FILE, "w") as f:
        json.dump(card_data, f, indent=4)

def fetch_card_data():
    """Fetch all valid card names, sets, and rarities from LimitlessTCG."""
    response = requests.get(CARD_LIST_URL)
    if response.status_code != 200:
        print("Received not 200 from LimitlessTCG")
        return []

    soup = BeautifulSoup(response.text, 'html.parser')
    set_links = soup.select("table.sets-table a[href]")
    
    card_data = []
    fetched_urls = set()  # Set to track already visited URLs

    for link in set_links:
        set_url = BASE_URL + link["href"]
        
        if "P-A" in set_url:
            print(f"Skipping set: {set_url}")
            continue

        # If this set URL has already been fetched, skip it
        if set_url in fetched_urls:
            continue

        print(f"Fetching data for set: {link.text.strip()}")

        set_response = requests.get(set_url)
        if set_response.status_code != 200:
            continue
        
        set_soup = BeautifulSoup(set_response.text, 'html.parser')
        card_links = set_soup.select(".card-search-grid a[href]")
        
        for card_link in card_links:
            card_url = BASE_URL + card_link["href"]

            # If this card URL has already been fetched, skip it
            if card_url in fetched_urls:
                continue

            print(f"Fetching card data from: {card_url}")

            card_response = requests.get(card_url)
            if card_response.status_code != 200:
                continue

            card_soup = BeautifulSoup(card_response.text, 'html.parser')
            
            # Extract card name (adjust the selector if needed)
            try:
                card_name = card_soup.select_one(".card-text-name a").text.strip()
            except AttributeError:
                print(f"Error: Failed to extract card name for {card_url}")
                continue

            # Extract rarity (adjust the selector if needed)
            try:
                rarity_div = card_soup.find('div', class_='card-prints-current')
                rarity_span = rarity_div.find_all('span')[1]
                card_rarity = rarity_span.text.strip().split('·')[1].strip()
                card_rarity = card_rarity.replace('◊', 'D')  # Replace diamond with 'D'
                card_rarity = card_rarity.replace('\25ca', 'D')  # Replace diamond with 'D'
                card_rarity = card_rarity.replace('★', 'S')  # Replace star with 'S'
                card_rarity = card_rarity.replace('\u2606', 'S')  # In case the star is represented as unicode
            except AttributeError:
                print(f"Error: Failed to extract rarity for {card_url}")
                card_rarity = "Unknown"  # Default if not found

            # Add data for this card, including the set name
            card_data.append({
                "name": card_name,
                "set": link.text.strip(),  # Use set name from the parent link
                "rarity": card_rarity
            })
            print(card_data)

            fetched_urls.add(card_url)  # Track that we've already visited this card URL
        
        fetched_urls.add(set_url)  # Track that we've already visited this set URL

    # Log the first few cards to verify correct scraping
    print(f"Scraped {len(card_data)} cards.")
    if card_data:
        print(f"Sample data: {card_data[:5]}")  # Print first 5 cards for inspection

    return card_data


# Initially load saved card data, if available
valid_cards = load_card_data()


data = load_data()

intents = discord.Intents.default()
intents.message_content = True  # Enable the message content intent
bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user}')
    auto_save.start()

@bot.command()
async def add_trade(ctx, *, card_name: str, set_name: str):
    """Add a card to your trade list."""
    if not any(card["name"].lower() == card_name.lower() for card in valid_cards):
        await ctx.send(f'**{card_name}** is not a valid Pokémon TCG card.')
        return
    if not any(card["name"].lower() == card_name.lower() for card in valid_cards):
        await ctx.send(f'**{card_name}** is not a valid Pokémon TCG card.')
        return    
    user_id = str(ctx.author.id)
    data.setdefault(user_id, {"trade": [], "wishlist": []})
    if card_name not in data[user_id]["trade"]:
        data[user_id]["trade"].append(card_name)
        await ctx.send(f'Added **{card_name}** to your trade list.')
    else:
        await ctx.send(f'**{card_name}** is already in your trade list.')

@bot.command()
async def add_wishlist(ctx, *, card_name: str):
    """Add a card to your wishlist."""
    if not any(card["name"].lower() == card_name.lower() for card in valid_cards):
        await ctx.send(f'**{card_name}** is not a valid Pokémon TCG card.')
        return
    user_id = str(ctx.author.id)
    data.setdefault(user_id, {"trade": [], "wishlist": []})
    if card_name not in data[user_id]["wishlist"]:
        data[user_id]["wishlist"].append(card_name)
        await ctx.send(f'Added **{card_name}** to your wishlist.')
    else:
        await ctx.send(f'**{card_name}** is already in your wishlist.')

@bot.command()
async def remove_trade(ctx, *, card_name: str):
    """Remove a card from your trade list."""
    user_id = str(ctx.author.id)
    if user_id in data and card_name in data[user_id]["trade"]:
        data[user_id]["trade"].remove(card_name)
        await ctx.send(f'Removed **{card_name}** from your trade list.')
    else:
        await ctx.send(f'**{card_name}** is not in your trade list.')

@bot.command()
async def remove_wishlist(ctx, *, card_name: str):
    """Remove a card from your wishlist."""
    user_id = str(ctx.author.id)
    if user_id in data and card_name in data[user_id]["wishlist"]:
        data[user_id]["wishlist"].remove(card_name)
        await ctx.send(f'Removed **{card_name}** from your wishlist.')
    else:
        await ctx.send(f'**{card_name}** is not in your wishlist.')

@bot.command()
async def view_lists(ctx, member: discord.Member = None):
    """View your or another user's trade and wishlist."""
    member = member or ctx.author
    user_id = str(member.id)
    user_data = data.get(user_id, {"trade": [], "wishlist": []})
    
    trade_list = "\n".join(user_data["trade"]) or "None"
    wishlist = "\n".join(user_data["wishlist"]) or "None"
    
    embed = discord.Embed(title=f"{member.display_name}'s Lists", color=discord.Color.blue())
    embed.add_field(name="Trade List", value=trade_list, inline=False)
    embed.add_field(name="Wishlist", value=wishlist, inline=False)
    
    await ctx.send(embed=embed)

# Global error handler
@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandNotFound):
        await ctx.send("Sorry, I couldn't find that command. Please check the command and try again.")
    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.send(f"Oops! It seems you're missing some required arguments. Please check the command syntax.")
    elif isinstance(error, requests.exceptions.RequestException):
        # Handle network-related issues (e.g., failed web scrape)
        await ctx.send("There was an issue connecting to the external service. Please try again later.")
    else:
        # For all other errors, just print them and reply with a generic error message
        print(f"An error occurred: {error}")
        await ctx.send("An unexpected error occurred. Please try again later.")

@bot.command()
async def scrape(ctx):
    """Manually trigger a web scrape to update the card data."""
    # Delete the command message
    await ctx.message.delete()

    await ctx.send("Starting scrape... Please wait.")
    valid_cards = fetch_card_data()
    save_card_data(valid_cards)
    await ctx.send(f"Scraping complete. Fetched {len(valid_cards)} cards.")
    
@bot.command()
async def hello(ctx):
    await ctx.send("GIBLE!")

@tasks.loop(minutes=5)
async def auto_save():
    save_data(data)
    print("Data saved.")

load_dotenv()
TOKEN = os.getenv("DISCORD_BOT_TOKEN")
bot.run(TOKEN)
