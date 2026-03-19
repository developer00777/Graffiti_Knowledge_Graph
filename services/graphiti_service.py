"""
CHAMP Graph service wrapper for knowledge graph operations.

Provides a high-level interface for ingesting multi-modal data
(emails, calls, SMS, LinkedIn, meetings) and querying the
knowledge graph.
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
    - Generic episode ingestion (any data source)
    - Email ingestion (convenience wrappers)
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

    # === Generic ingestion methods (any data source) ===

    async def ingest_episode(
        self,
        content: str,
        name: str,
        account_name: str,
        source_description: str,
        reference_time: datetime,
        source: EpisodeType = EpisodeType.message,
    ) -> None:
        """
        Ingest a single episode from any data source.

        This is the core generic ingestion method. All source-specific
        convenience methods (ingest_email, etc.) delegate to this.

        Parameters
        ----------
        content : str
            Formatted text content for LLM extraction
        name : str
            Human-readable episode name (e.g., "Email: Subject line")
        account_name : str
            Name of the account (used as group_id)
        source_description : str
            Description of the data source (e.g., "Email via email (outbound)")
        reference_time : datetime
            When this interaction occurred
        source : EpisodeType
            Graphiti episode type classification
        """
        if not self.client:
            raise RuntimeError("Not connected. Call connect() first.")

        group_id = self._normalize_group_id(account_name)

        logger.debug(f"Ingesting episode: {name[:50]} to group {group_id}")

        await self.client.add_episode(
            name=name,
            episode_body=content,
            source=source,
            source_description=source_description,
            reference_time=reference_time,
            group_id=group_id,
            entity_types=self.entity_types,
            edge_types=self.edge_types,
            edge_type_map=self.edge_type_map,
        )

    async def ingest_episodes_bulk(
        self,
        episodes: List[Dict[str, Any]],
        account_name: str,
    ) -> None:
        """
        Bulk ingest multiple episodes from any data source.

        Parameters
        ----------
        episodes : list of dict
            Each dict must have keys: name, content, reference_time, source_description.
            Optional keys: source (defaults to EpisodeType.message).
        account_name : str
            Name of the account (used as group_id)
        """
        if not self.client:
            raise RuntimeError("Not connected. Call connect() first.")

        if not episodes:
            return

        group_id = self._normalize_group_id(account_name)

        raw_episodes = [
            RawEpisode(
                name=ep['name'],
                content=ep['content'],
                reference_time=ep['reference_time'],
                source=ep.get('source', EpisodeType.message),
                source_description=ep['source_description'],
            )
            for ep in episodes
        ]

        logger.info(f"Bulk ingesting {len(episodes)} episodes to group {group_id}")

        await self.client.add_episode_bulk(
            raw_episodes,
            group_id=group_id,
            entity_types=self.entity_types,
            edge_types=self.edge_types,
            edge_type_map=self.edge_type_map,
        )

    # === Email convenience wrappers (backward compatible) ===

    async def ingest_email(
        self,
        email: Email,
        account_name: str
    ) -> None:
        """
        Ingest a single email as an episode.

        Convenience wrapper around ingest_episode() for email data.

        Parameters
        ----------
        email : Email
            The email to ingest
        account_name : str
            Name of the account (used as group_id)
        """
        await self.ingest_episode(
            content=email.to_episode_content(),
            name=f"Email: {email.subject[:50]}",
            account_name=account_name,
            source_description=f"Email via {email.channel} ({email.direction.value})",
            reference_time=email.timestamp,
            source=EpisodeType.message,
        )

    async def ingest_emails_bulk(
        self,
        emails: List[Email],
        account_name: str
    ) -> None:
        """
        Bulk ingest multiple emails.

        Convenience wrapper around ingest_episodes_bulk() for email data.

        Parameters
        ----------
        emails : list of Email
            Emails to ingest
        account_name : str
            Name of the account (used as group_id)
        """
        if not emails:
            return

        episodes = [
            {
                'name': f"Email: {email.subject[:50]}",
                'content': email.to_episode_content(),
                'reference_time': email.timestamp,
                'source': EpisodeType.message,
                'source_description': f"Email via {email.channel} ({email.direction.value})",
            }
            for email in emails
        ]

        await self.ingest_episodes_bulk(episodes, account_name)

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

    # === Timeline & Relationship Map ===

    async def query_timeline(
        self,
        account_name: str,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """
        Get cross-channel communication timeline.

        Returns episodes ordered by time, enriched with channel metadata.
        """
        if not self.client:
            raise RuntimeError("Not connected. Call connect() first.")

        group_id = self._normalize_group_id(account_name)

        episodes = await self.client.retrieve_episodes(
            reference_time=datetime.now(timezone.utc),
            last_n=limit,
            group_ids=[group_id],
        )

        timeline = []
        for e in episodes:
            source_desc = e.source_description if hasattr(e, 'source_description') else ''
            ep_name = e.name if hasattr(e, 'name') else ''
            channel = self._detect_channel(source_desc or ep_name or '')
            direction = self._detect_direction(source_desc or '')
            summary = None
            if e.content:
                summary = (e.content[:200] + '...') if len(e.content) > 200 else e.content

            timeline.append({
                'timestamp': e.valid_at.isoformat() if e.valid_at else None,
                'channel': channel,
                'name': ep_name,
                'summary': summary,
                'direction': direction,
            })

        return timeline

    async def query_relationship_map(self, account_name: str) -> List[Dict[str, Any]]:
        """
        Get contact relationship map for an account.

        Returns all edges with resolved source/target names.
        """
        results = await self.search_account(
            account_name,
            "All relationships, org structure, reporting lines, interactions between contacts and team members",
            num_results=200,
        )

        node_names = {n['uuid']: n['name'] for n in results.get('nodes', [])}

        relationships = []
        for edge in results.get('edges', []):
            source_name = node_names.get(edge.get('source_node_uuid'), 'Unknown')
            target_name = node_names.get(edge.get('target_node_uuid'), 'Unknown')
            relationships.append({
                'source': source_name,
                'target': target_name,
                'relationship_type': edge.get('name', ''),
                'fact': edge.get('fact'),
                'valid_at': edge.get('valid_at'),
            })

        return relationships

    # === Intelligence queries ===

    async def query_cross_salesperson_overlap(
        self,
        account_name: str,
    ) -> List[Dict[str, Any]]:
        """
        Find contacts engaged by multiple team members.

        Returns contacts with 2+ team members, sorted by overlap count.
        """
        results = await self.search_account(
            account_name,
            "Which contacts have been contacted by multiple team members? Show all team member interactions with each contact.",
            num_results=200,
        )

        node_info = {n['uuid']: n for n in results.get('nodes', [])}
        contact_team_map: Dict[str, Dict] = {}

        for edge in results.get('edges', []):
            source = node_info.get(edge.get('source_node_uuid'), {})
            target = node_info.get(edge.get('target_node_uuid'), {})
            source_labels = source.get('labels', [])
            target_labels = target.get('labels', [])

            contact_uuid = None
            team_member_name = None

            if 'TeamMember' in source_labels and 'Contact' in target_labels:
                contact_uuid = edge['target_node_uuid']
                team_member_name = source.get('name', 'Unknown')
            elif 'Contact' in source_labels and 'TeamMember' in target_labels:
                contact_uuid = edge['source_node_uuid']
                team_member_name = target.get('name', 'Unknown')

            if contact_uuid and team_member_name:
                if contact_uuid not in contact_team_map:
                    contact_node = node_info.get(contact_uuid, {})
                    contact_team_map[contact_uuid] = {
                        'contact_name': contact_node.get('name', 'Unknown'),
                        'team_members': set(),
                        'interactions': [],
                    }
                contact_team_map[contact_uuid]['team_members'].add(team_member_name)
                contact_team_map[contact_uuid]['interactions'].append({
                    'team_member': team_member_name,
                    'type': edge.get('name'),
                    'fact': edge.get('fact'),
                })

        overlaps = []
        for data in contact_team_map.values():
            if len(data['team_members']) >= 2:
                overlaps.append({
                    'contact_name': data['contact_name'],
                    'team_members': sorted(data['team_members']),
                    'team_member_count': len(data['team_members']),
                    'interactions': data['interactions'],
                })

        return sorted(overlaps, key=lambda x: x['team_member_count'], reverse=True)

    async def query_stakeholder_map(
        self,
        account_name: str,
    ) -> List[Dict[str, Any]]:
        """
        Map stakeholders: champions, blockers, decision-makers per account.

        Uses INVOLVED_IN, REPORTS_TO, and WORKS_AT edges.
        """
        results = await self.search_account(
            account_name,
            "Who are the champions, blockers, decision-makers, influencers, and technical evaluators? What are their roles in opportunities?",
            num_results=200,
        )

        node_names = {n['uuid']: n['name'] for n in results.get('nodes', [])}
        stakeholders = []

        for edge in results.get('edges', []):
            edge_name = (edge.get('name') or '').upper()
            if edge_name in ['INVOLVED_IN', 'REPORTS_TO', 'WORKS_AT']:
                source_name = node_names.get(edge.get('source_node_uuid'), 'Unknown')
                target_name = node_names.get(edge.get('target_node_uuid'), 'Unknown')
                stakeholders.append({
                    'person': source_name,
                    'relationship': edge_name,
                    'target': target_name,
                    'fact': edge.get('fact', ''),
                    'valid_at': edge.get('valid_at'),
                })

        return stakeholders

    async def query_engagement_gaps(
        self,
        account_name: str,
        days_threshold: int = 30,
    ) -> List[Dict[str, Any]]:
        """
        Find contacts not interacted with recently.

        Compares contacts list against recent episodes to find gaps.
        """
        contacts_results = await self.search_account(
            account_name,
            "All contacts and people at this account",
            num_results=200,
        )

        recent = await self.query_recent_communications(account_name, limit=100)

        # Build set of names found in recent communications
        recent_names = set()
        for comm in recent:
            content_lower = (comm.get('content', '') or '').lower()
            for node in contacts_results.get('nodes', []):
                node_name = node.get('name', '')
                if node_name and node_name.lower() in content_lower:
                    recent_names.add(node_name.lower())

        gaps = []
        for node in contacts_results.get('nodes', []):
            labels = node.get('labels', [])
            if 'Contact' in labels:
                name = node.get('name', '')
                if name.lower() not in recent_names:
                    gaps.append({
                        'contact_name': name,
                        'last_known_interaction': node.get('created_at'),
                        'summary': node.get('summary'),
                    })

        return gaps

    async def query_cross_branch_connections(
        self,
        account_name: str,
    ) -> List[Dict[str, Any]]:
        """
        Find connections across branches/divisions of an account.
        """
        results = await self.search_account(
            account_name,
            "What branches, divisions, and business units exist? Which contacts belong to which branch?",
            num_results=200,
        )

        node_names = {n['uuid']: n['name'] for n in results.get('nodes', [])}
        branches = []

        for edge in results.get('edges', []):
            edge_name = (edge.get('name') or '').upper()
            if edge_name == 'BELONGS_TO_BRANCH':
                source_name = node_names.get(edge.get('source_node_uuid'), 'Unknown')
                target_name = node_names.get(edge.get('target_node_uuid'), 'Unknown')
                branches.append({
                    'entity': source_name,
                    'branch': target_name,
                    'fact': edge.get('fact'),
                })

        return branches

    async def query_combined_opportunities(
        self,
        account_name: str,
    ) -> List[Dict[str, Any]]:
        """
        Detect opportunities and who is involved (champions, blockers, etc.).
        """
        results = await self.search_account(
            account_name,
            "What sales opportunities exist? Who is involved as champion, blocker, decision-maker?",
            num_results=200,
        )

        node_info = {n['uuid']: n for n in results.get('nodes', [])}

        opportunities: Dict[str, Dict] = {}
        for node in results.get('nodes', []):
            if 'Opportunity' in node.get('labels', []):
                opportunities[node['uuid']] = {
                    'name': node.get('name'),
                    'summary': node.get('summary'),
                    'attributes': node.get('attributes', {}),
                    'involved': [],
                }

        for edge in results.get('edges', []):
            edge_name = (edge.get('name') or '').upper()
            target_uuid = edge.get('target_node_uuid')

            if edge_name == 'INVOLVED_IN' and target_uuid in opportunities:
                source = node_info.get(edge.get('source_node_uuid'), {})
                opportunities[target_uuid]['involved'].append({
                    'person': source.get('name', 'Unknown'),
                    'role': edge.get('fact', ''),
                })
            elif edge_name == 'HAS_OPPORTUNITY' and target_uuid in opportunities:
                source = node_info.get(edge.get('source_node_uuid'), {})
                opportunities[target_uuid]['account'] = source.get('name', 'Unknown')

        return list(opportunities.values())

    # === Helper methods ===

    def _normalize_group_id(self, account_name: str) -> str:
        """Normalize account name to valid group_id"""
        return account_name.lower().replace(' ', '-').replace('.', '-').replace('_', '-')

    def _detect_channel(self, text: str) -> str:
        """Detect communication channel from source description or name."""
        text_lower = text.lower()
        if 'email' in text_lower:
            return 'email'
        if 'call' in text_lower or 'phone' in text_lower:
            return 'call'
        if 'text' in text_lower or 'sms' in text_lower or 'whatsapp' in text_lower:
            return 'sms'
        if 'linkedin' in text_lower or 'social' in text_lower or 'twitter' in text_lower:
            return 'social'
        if 'meeting' in text_lower:
            return 'meeting'
        return 'unknown'

    def _detect_direction(self, text: str) -> Optional[str]:
        """Detect communication direction from source description."""
        text_lower = text.lower()
        if 'outbound' in text_lower:
            return 'outbound'
        if 'inbound' in text_lower:
            return 'inbound'
        return None

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
            'Opportunity': '#FFB347',
            'Branch': '#FF69B4',
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
