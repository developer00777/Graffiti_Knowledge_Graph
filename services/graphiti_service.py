"""
Graphiti service wrapper for email knowledge graph operations.

Provides a high-level interface for ingesting emails and querying
the knowledge graph.
"""
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from graphiti_core import Graphiti
from graphiti_core.llm_client import LLMClient, OpenAIClient
from graphiti_core.embedder import EmbedderClient, OpenAIEmbedder
from graphiti_core.nodes import EpisodeType
from graphiti_core.utils.bulk_utils import RawEpisode
from graphiti_core.search.search_config_recipes import (
    COMBINED_HYBRID_SEARCH_RRF,
    NODE_HYBRID_SEARCH_RRF,
    EDGE_HYBRID_SEARCH_RRF,
)

from config.entity_types import ENTITY_TYPES
from config.edge_types import EDGE_TYPES, EDGE_TYPE_MAP
from models.email import Email

logger = logging.getLogger(__name__)


class GraphitiService:
    """
    Service wrapper for Graphiti knowledge graph operations.

    Handles:
    - Connection management
    - Email ingestion (single and bulk)
    - Search and query operations
    - Graph visualization export
    """

    def __init__(
        self,
        neo4j_uri: str,
        neo4j_user: str,
        neo4j_password: str,
        openai_api_key: Optional[str] = None,
        openai_base_url: Optional[str] = None,
        model_name: Optional[str] = None,
    ):
        """
        Initialize GraphitiService.

        Parameters
        ----------
        neo4j_uri : str
            Neo4j bolt URI (e.g., "bolt://localhost:7687")
        neo4j_user : str
            Neo4j username
        neo4j_password : str
            Neo4j password
        openai_api_key : str, optional
            API key for LLM (OpenAI or OpenRouter)
        openai_base_url : str, optional
            Base URL for API (for OpenRouter: "https://openrouter.ai/api/v1")
        model_name : str, optional
            Model name to use
        """
        self.neo4j_uri = neo4j_uri
        self.neo4j_user = neo4j_user
        self.neo4j_password = neo4j_password
        self.openai_api_key = openai_api_key
        self.openai_base_url = openai_base_url
        self.model_name = model_name

        self.client: Optional[Graphiti] = None

        # Entity and edge type configuration
        self.entity_types = ENTITY_TYPES
        self.edge_types = EDGE_TYPES
        self.edge_type_map = EDGE_TYPE_MAP

    async def connect(self) -> None:
        """Initialize Graphiti client and build indices"""
        logger.info(f"Connecting to Neo4j at {self.neo4j_uri}")

        # Create LLM client with OpenRouter configuration if specified
        llm_client = None
        embedder = None

        if self.openai_api_key:
            llm_client = OpenAIClient(
                api_key=self.openai_api_key,
                base_url=self.openai_base_url,
                model=self.model_name,
            )
            embedder = OpenAIEmbedder(
                api_key=self.openai_api_key,
                base_url=self.openai_base_url,
            )

        self.client = Graphiti(
            uri=self.neo4j_uri,
            user=self.neo4j_user,
            password=self.neo4j_password,
            llm_client=llm_client,
            embedder=embedder,
        )

        # Build indices and constraints
        await self.client.build_indices_and_constraints()
        logger.info("Graphiti connection established and indices built")

    async def disconnect(self) -> None:
        """Close Graphiti connection"""
        if self.client:
            await self.client.close()
            self.client = None
        logger.info("Graphiti connection closed")

    async def ingest_email(
        self,
        email: Email,
        account_name: str
    ) -> None:
        """
        Ingest a single email as an episode.

        Parameters
        ----------
        email : Email
            The email to ingest
        account_name : str
            Name of the account (used as group_id)
        """
        if not self.client:
            raise RuntimeError("Not connected. Call connect() first.")

        episode_content = email.to_episode_content()
        group_id = self._normalize_group_id(account_name)

        logger.debug(f"Ingesting email: {email.subject[:50]} to group {group_id}")

        await self.client.add_episode(
            name=f"Email: {email.subject[:50]}",
            episode_body=episode_content,
            source=EpisodeType.message,
            source_description=f"Email via {email.channel} ({email.direction.value})",
            reference_time=email.timestamp,
            group_id=group_id,
            entity_types=self.entity_types,
            edge_types=self.edge_types,
            edge_type_map=self.edge_type_map,
        )

    async def ingest_emails_bulk(
        self,
        emails: List[Email],
        account_name: str
    ) -> None:
        """
        Bulk ingest multiple emails.

        Parameters
        ----------
        emails : list of Email
            Emails to ingest
        account_name : str
            Name of the account (used as group_id)
        """
        if not self.client:
            raise RuntimeError("Not connected. Call connect() first.")

        if not emails:
            return

        group_id = self._normalize_group_id(account_name)

        raw_episodes = [
            RawEpisode(
                name=f"Email: {email.subject[:50]}",
                content=email.to_episode_content(),
                reference_time=email.timestamp,
                source=EpisodeType.message,
                source_description=f"Email via {email.channel} ({email.direction.value})",
            )
            for email in emails
        ]

        logger.info(f"Bulk ingesting {len(emails)} emails to group {group_id}")

        await self.client.add_episode_bulk(
            raw_episodes,
            group_id=group_id,
            entity_types=self.entity_types,
            edge_types=self.edge_types,
            edge_type_map=self.edge_type_map,
        )

    async def search_account(
        self,
        account_name: str,
        query: str,
        num_results: int = 20
    ) -> Dict[str, Any]:
        """
        Search within an account's knowledge graph.

        Parameters
        ----------
        account_name : str
            Account to search within
        query : str
            Search query
        num_results : int
            Maximum results to return

        Returns
        -------
        dict
            Search results with nodes, edges, and communities
        """
        if not self.client:
            raise RuntimeError("Not connected. Call connect() first.")

        group_id = self._normalize_group_id(account_name)

        results = await self.client._search(
            query=query,
            group_ids=[group_id],
            config=COMBINED_HYBRID_SEARCH_RRF,
        )

        return {
            'nodes': [self._node_to_dict(n) for n in results.nodes],
            'edges': [self._edge_to_dict(e) for e in results.edges],
            'communities': [self._community_to_dict(c) for c in results.communities],
        }

    async def get_account_graph(self, account_name: str) -> Dict[str, Any]:
        """
        Get full knowledge graph for visualization.

        Parameters
        ----------
        account_name : str
            Account to get graph for

        Returns
        -------
        dict
            Graph data with nodes and edges for D3/Cytoscape
        """
        # Search for all entities
        results = await self.search_account(
            account_name,
            f"All people, communications, topics, and relationships",
            num_results=200
        )

        return self._format_for_visualization(results)

    # === Pre-built query methods ===

    async def query_who_reached_out(self, account_name: str) -> List[Dict]:
        """Who from our team contacted this account?"""
        results = await self.search_account(
            account_name,
            "Who from our team sent emails or contacted people at this account?"
        )
        return results['edges']

    async def query_discussions_by_person(
        self,
        account_name: str,
        person_name: str
    ) -> List[Dict]:
        """What did a specific person discuss?"""
        results = await self.search_account(
            account_name,
            f"What topics and subjects did {person_name} discuss in emails?"
        )
        return results['edges']

    async def query_communication_channels(self, account_name: str) -> List[Dict]:
        """Which channels were used?"""
        results = await self.search_account(
            account_name,
            "What communication channels were used? Email, phone, LinkedIn, meetings?"
        )
        return results['edges']

    async def query_personal_details(self, account_name: str) -> List[Dict]:
        """Personal tidbits about contacts"""
        results = await self.search_account(
            account_name,
            "What personal details do we know about contacts? Kids, family, hobbies, interests, preferences?"
        )
        return results['edges']

    async def query_recent_communications(
        self,
        account_name: str,
        limit: int = 10
    ) -> List[Dict]:
        """Most recent communications"""
        if not self.client:
            raise RuntimeError("Not connected. Call connect() first.")

        group_id = self._normalize_group_id(account_name)

        episodes = await self.client.retrieve_episodes(
            reference_time=datetime.now(timezone.utc),
            last_n=limit,
            group_ids=[group_id],
        )

        return [
            {
                'name': e.name,
                'content': e.content[:500] if e.content else '',
                'timestamp': e.valid_at.isoformat() if e.valid_at else None,
            }
            for e in episodes
        ]

    async def query_contact_relationships(self, account_name: str) -> List[Dict]:
        """Relationships between contacts within the account"""
        results = await self.search_account(
            account_name,
            "What are the reporting relationships and organizational structure? Who reports to whom?"
        )
        return results['edges']

    # === Helper methods ===

    def _normalize_group_id(self, account_name: str) -> str:
        """Normalize account name to valid group_id"""
        return account_name.lower().replace(' ', '-').replace('.', '-').replace('_', '-')

    def _node_to_dict(self, node) -> Dict[str, Any]:
        """Convert node to dictionary"""
        return {
            'uuid': node.uuid,
            'name': node.name,
            'labels': node.labels if hasattr(node, 'labels') else [],
            'summary': node.summary if hasattr(node, 'summary') else None,
            'attributes': node.attributes if hasattr(node, 'attributes') else {},
            'created_at': node.created_at.isoformat() if hasattr(node, 'created_at') and node.created_at else None,
        }

    def _edge_to_dict(self, edge) -> Dict[str, Any]:
        """Convert edge to dictionary"""
        return {
            'uuid': edge.uuid,
            'name': edge.name if hasattr(edge, 'name') else None,
            'fact': edge.fact if hasattr(edge, 'fact') else None,
            'source_node_uuid': edge.source_node_uuid if hasattr(edge, 'source_node_uuid') else None,
            'target_node_uuid': edge.target_node_uuid if hasattr(edge, 'target_node_uuid') else None,
            'valid_at': edge.valid_at.isoformat() if hasattr(edge, 'valid_at') and edge.valid_at else None,
            'invalid_at': edge.invalid_at.isoformat() if hasattr(edge, 'invalid_at') and edge.invalid_at else None,
        }

    def _community_to_dict(self, community) -> Dict[str, Any]:
        """Convert community to dictionary"""
        return {
            'uuid': community.uuid,
            'name': community.name,
            'summary': community.summary if hasattr(community, 'summary') else None,
        }

    def _format_for_visualization(self, results: Dict) -> Dict[str, Any]:
        """Format results for D3.js/Cytoscape visualization"""
        # Color scheme by node type
        colors = {
            'Contact': '#4ECDC4',
            'Account': '#FF6B6B',
            'TeamMember': '#45B7D1',
            'Topic': '#96CEB4',
            'PersonalDetail': '#FFEAA7',
            'Communication': '#DDA0DD',
            'Entity': '#999999',
        }

        nodes = []
        for node in results.get('nodes', []):
            node_type = node['labels'][0] if node.get('labels') else 'Entity'
            nodes.append({
                'id': node['uuid'],
                'label': node['name'],
                'type': node_type,
                'color': colors.get(node_type, '#999999'),
                'size': 10,
                'properties': node.get('attributes', {}),
            })

        edges = []
        for edge in results.get('edges', []):
            edges.append({
                'id': edge['uuid'],
                'source': edge['source_node_uuid'],
                'target': edge['target_node_uuid'],
                'label': edge.get('name', ''),
                'fact': edge.get('fact', ''),
                'valid_at': edge.get('valid_at'),
            })

        return {'nodes': nodes, 'edges': edges}
