import discord
from discord import app_commands
import os
import json
import logging
from redis import Redis
from app.nlp.preprocessor import TextPreprocessor
from app.models.database import SessionLocal
from app.models.feedback import Feedback
from app.models.cluster import Cluster
from app.models.initiative import Initiative
from app.models.label import Label
from app.models.product_area import ProductArea
from sqlalchemy.orm import joinedload
from sqlalchemy import func
from app.models.feedback_label import FeedbackLabel

logger = logging.getLogger(__name__)

class ProductSyncBot(discord.Client):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.guilds = True
        
        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(self)
        
        # Initialize components
        self.redis_client = Redis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379"))
        self.preprocessor = TextPreprocessor()
        self.db = SessionLocal()
        
        # Register commands
        self._register_commands()
    
    def _register_commands(self):
        """Register slash commands."""
        
        @self.tree.command(name="feedback", description="Add feedback")
        @app_commands.describe(
            text="Your feedback text",
            product_area="Product area (optional)"
        )
        async def add_feedback(interaction: discord.Interaction, text: str, product_area: str = None):
            """Add feedback as specified in README."""
            try:
                # Check if user is in a thread or channel
                if isinstance(interaction.channel, discord.Thread):
                    context = f"Thread: {interaction.channel.name}"
                else:
                    context = f"Channel: {interaction.channel.name}"
                
                # Create feedback payload
                payload = {
                    'source': 'discord',
                    'source_msg_id': str(interaction.id),
                    'author_id': str(interaction.user.id),
                    'text': text,
                    'channel': str(interaction.channel.id),
                    'context': context,
                    'product_area': product_area,
                    'created_at': interaction.created_at.isoformat()
                }
                
                # Check for duplicate
                key = f"dupe:discord:{interaction.id}"
                if self.redis_client.setnx(key, 1):
                    self.redis_client.expire(key, 7 * 24 * 3600)  # 7 days
                    self.redis_client.lpush("ingest:feedback", json.dumps(payload))
                    
                    # Create embed response
                    embed = discord.Embed(
                        title="Feedback Added",
                        description=f"Your feedback has been queued for processing.",
                        color=discord.Color.green()
                    )
                    embed.add_field(name="Text", value=text[:100] + "..." if len(text) > 100 else text, inline=False)
                    if product_area:
                        embed.add_field(name="Product Area", value=product_area, inline=True)
                    embed.add_field(name="Context", value=context, inline=True)
                    embed.add_field(name="Status", value="Queued", inline=True)
                    
                    await interaction.response.send_message(embed=embed, ephemeral=True)
                    logger.info(f"Queued Discord feedback from {interaction.user.name}")
                else:
                    await interaction.response.send_message("This feedback has already been submitted.", ephemeral=True)
                    
            except Exception as e:
                logger.error(f"Failed to add feedback: {e}")
                await interaction.response.send_message("Failed to add feedback. Please try again.", ephemeral=True)
        
        @self.tree.command(name="status", description="Check feedback status")
        @app_commands.describe(
            feedback_id="Feedback ID to check"
        )
        async def check_status(interaction: discord.Interaction, feedback_id: int):
            """Check feedback status as specified in README."""
            try:
                feedback = self.db.query(Feedback).filter(Feedback.id == feedback_id).first()
                
                if not feedback:
                    await interaction.response.send_message("Feedback not found.", ephemeral=True)
                    return
                
                # Get labels
                labels = self.db.query(Label).join(FeedbackLabel).filter(
                    FeedbackLabel.feedback_id == feedback.id
                ).all()
                
                # Get cluster info
                cluster_info = ""
                if feedback.cluster_id:
                    cluster = self.db.query(Cluster).filter(Cluster.id == feedback.cluster_id).first()
                    if cluster:
                        cluster_info = f"Cluster {cluster.id} (Size: {cluster.size})"
                
                # Get JIRA info
                jira_info = ""
                if feedback.cluster_id:
                    initiative = self.db.query(Initiative).filter(Initiative.cluster_id == feedback.cluster_id).first()
                    if initiative and initiative.jira_key:
                        jira_info = f"JIRA: {initiative.jira_key}"
                
                # Create embed response
                embed = discord.Embed(
                    title=f"Feedback Status #{feedback_id}",
                    color=discord.Color.blue()
                )
                embed.add_field(name="Source", value=feedback.source, inline=True)
                embed.add_field(name="Status", value=feedback.status, inline=True)
                embed.add_field(name="Priority", value=f"{feedback.priority_score:.2f}" if feedback.priority_score else "N/A", inline=True)
                embed.add_field(name="Text", value=feedback.text_raw[:100] + "..." if len(feedback.text_raw) > 100 else feedback.text_raw, inline=False)
                
                if labels:
                    label_names = [l.name for l in labels]
                    embed.add_field(name="Labels", value=", ".join(label_names), inline=False)
                
                if cluster_info:
                    embed.add_field(name="Cluster", value=cluster_info, inline=True)
                
                if jira_info:
                    embed.add_field(name="JIRA", value=jira_info, inline=True)
                
                await interaction.response.send_message(embed=embed, ephemeral=True)
                
            except Exception as e:
                logger.error(f"Failed to check status: {e}")
                await interaction.response.send_message("Failed to check status. Please try again.", ephemeral=True)
        
        @self.tree.command(name="top", description="Show top clusters by priority")
        @app_commands.describe(
            product_area="Product area to filter by (optional)",
            limit="Number of clusters to show (default: 5)"
        )
        async def show_top_clusters(interaction: discord.Interaction, product_area: str = None, limit: int = 5):
            """Show top clusters as specified in README."""
            try:
                # Build query
                query = self.db.query(Cluster).join(Feedback).filter(
                    Feedback.priority_score.isnot(None)
                )
                
                if product_area:
                    query = query.join(ProductArea).filter(ProductArea.name == product_area)
                
                # Get top clusters by average priority
                top_clusters = query.group_by(Cluster.id).order_by(
                    func.avg(Feedback.priority_score).desc()
                ).limit(limit).all()
                
                if not top_clusters:
                    await interaction.response.send_message("No clusters found.", ephemeral=True)
                    return
                
                # Create embed response
                embed = discord.Embed(
                    title=f"🏆 Top Clusters{f' in {product_area}' if product_area else ''}",
                    color=discord.Color.gold()
                )
                
                for i, cluster in enumerate(top_clusters, 1):
                    # Get average priority for this cluster
                    avg_priority = self.db.query(func.avg(Feedback.priority_score)).filter(
                        Feedback.cluster_id == cluster.id
                    ).scalar() or 0.0
                    
                    # Get sample feedback
                    sample_feedback = self.db.query(Feedback).filter(
                        Feedback.cluster_id == cluster.id
                    ).first()
                    
                    sample_text = sample_feedback.text_clean[:50] + "..." if sample_feedback and sample_feedback.text_clean else "No text"
                    
                    embed.add_field(
                        name=f"#{i} Cluster {cluster.id}",
                        value=f"Priority: {avg_priority:.2f}\nSize: {cluster.size}\nSample: {sample_text}",
                        inline=False
                    )
                
                await interaction.response.send_message(embed=embed, ephemeral=True)
                
            except Exception as e:
                logger.error(f"Failed to show top clusters: {e}")
                await interaction.response.send_message("Failed to show top clusters. Please try again.", ephemeral=True)
    
    async def setup_hook(self):
        """Sync commands when bot starts."""
        await self.tree.sync()
        logger.info("Discord bot commands synced")
    
    async def on_ready(self):
        """Bot ready event."""
        logger.info(f'Discord bot logged in as {self.user}')
        logger.info(f'Bot is in {len(self.guilds)} guilds')
    
    def __del__(self):
        """Cleanup on deletion."""
        if hasattr(self, 'db'):
            self.db.close()
        if hasattr(self, 'redis_client'):
            self.redis_client.close()

def run_discord_bot():
    """Run the Discord bot."""
    bot = ProductSyncBot()
    token = os.getenv("DISCORD_TOKEN")
    
    if not token:
        logger.error("DISCORD_TOKEN environment variable not set")
        return
    
    try:
        bot.run(token)
    except Exception as e:
        logger.error(f"Failed to run Discord bot: {e}")

if __name__ == "__main__":
    run_discord_bot() 