#!/usr/bin/env python3
"""
Test script to verify Graphiti and Neo4j setup.

Run this after starting Neo4j to verify everything is working.
"""
import asyncio
import os
import sys
from datetime import datetime, timezone

from dotenv import load_dotenv

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

load_dotenv()


async def test_neo4j_connection():
    """Test Neo4j connection"""
    print("\n1. Testing Neo4j connection...")

    from neo4j import GraphDatabase

    uri = os.getenv('NEO4J_URI', 'bolt://localhost:7687')
    user = os.getenv('NEO4J_USER', 'neo4j')
    password = os.getenv('NEO4J_PASSWORD', 'password')

    try:
        driver = GraphDatabase.driver(uri, auth=(user, password))
        with driver.session() as session:
            result = session.run("RETURN 'Hello, Neo4j!' AS message")
            record = result.single()
            print(f"   Neo4j says: {record['message']}")
        driver.close()
        print("   [OK] Neo4j connection successful!")
        return True
    except Exception as e:
        print(f"   [FAIL] Neo4j connection failed: {e}")
        return False


async def test_graphiti_init():
    """Test Graphiti initialization"""
    print("\n2. Testing Graphiti initialization...")

    try:
        from graphiti_core import Graphiti

        uri = os.getenv('NEO4J_URI', 'bolt://localhost:7687')
        user = os.getenv('NEO4J_USER', 'neo4j')
        password = os.getenv('NEO4J_PASSWORD', 'password')

        graphiti = Graphiti(uri, user, password)
        await graphiti.build_indices_and_constraints()
        print("   [OK] Graphiti initialized and indices built!")

        await graphiti.close()
        return True
    except Exception as e:
        print(f"   [FAIL] Graphiti initialization failed: {e}")
        return False


async def test_episode_ingestion():
    """Test episode ingestion"""
    print("\n3. Testing episode ingestion...")

    try:
        from graphiti_core import Graphiti
        from graphiti_core.nodes import EpisodeType

        uri = os.getenv('NEO4J_URI', 'bolt://localhost:7687')
        user = os.getenv('NEO4J_USER', 'neo4j')
        password = os.getenv('NEO4J_PASSWORD', 'password')

        graphiti = Graphiti(uri, user, password)

        # Ingest a test episode
        await graphiti.add_episode(
            name="Test Email",
            episode_body="""Email Communication Record
From: John Smith <john@acme.com>
To: Sarah Johnson <sarah@yourcompany.com>
Subject: Q4 Partnership Discussion
Date: 2024-12-15

Hi Sarah,

Great call today! I'm excited about the potential partnership.
My kids loved the baseball game last weekend - thanks for the tickets!

Let's schedule a follow-up next week to discuss pricing.

Best,
John
VP of Sales, Acme Corp""",
            source=EpisodeType.text,
            source_description="Test email",
            reference_time=datetime.now(timezone.utc),
            group_id="test-account"
        )

        print("   [OK] Test episode ingested!")
        await graphiti.close()
        return True
    except Exception as e:
        print(f"   [FAIL] Episode ingestion failed: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_search():
    """Test search functionality"""
    print("\n4. Testing search...")

    try:
        from graphiti_core import Graphiti

        uri = os.getenv('NEO4J_URI', 'bolt://localhost:7687')
        user = os.getenv('NEO4J_USER', 'neo4j')
        password = os.getenv('NEO4J_PASSWORD', 'password')

        graphiti = Graphiti(uri, user, password)

        results = await graphiti.search(
            "Who discussed partnership?",
            group_ids=["test-account"],
            num_results=5
        )

        print(f"   Found {len(results)} results")
        for r in results[:3]:
            fact = r.fact if hasattr(r, 'fact') else str(r)[:100]
            print(f"   - {fact[:80]}...")

        print("   [OK] Search working!")
        await graphiti.close()
        return True
    except Exception as e:
        print(f"   [FAIL] Search failed: {e}")
        return False


async def test_config_loading():
    """Test configuration loading"""
    print("\n5. Testing configuration...")

    try:
        from config.settings import get_settings
        from config.entity_types import ENTITY_TYPES
        from config.accounts import TOP_ACCOUNTS

        settings = get_settings()

        print(f"   Neo4j URI: {settings.neo4j_uri}")
        print(f"   OpenAI Base URL: {settings.openai_base_url}")
        print(f"   Model: {settings.model_name}")
        print(f"   Team domains: {settings.team_domain_list}")
        print(f"   Entity types defined: {len(ENTITY_TYPES)}")
        print(f"   Accounts configured: {len(TOP_ACCOUNTS)}")

        print("   [OK] Configuration loaded!")
        return True
    except Exception as e:
        print(f"   [FAIL] Config loading failed: {e}")
        return False


async def main():
    """Run all tests"""
    print("=" * 60)
    print("Email Knowledge Graph - Setup Verification")
    print("=" * 60)

    results = []

    # Test Neo4j
    results.append(await test_neo4j_connection())

    # Test Graphiti init
    if results[-1]:
        results.append(await test_graphiti_init())
    else:
        print("\n2. Skipping Graphiti test (Neo4j not connected)")
        results.append(False)

    # Test episode ingestion (only if Neo4j works)
    if results[0]:
        results.append(await test_episode_ingestion())
    else:
        print("\n3. Skipping ingestion test")
        results.append(False)

    # Test search (only if ingestion worked)
    if results[-1]:
        results.append(await test_search())
    else:
        print("\n4. Skipping search test")
        results.append(False)

    # Test config
    results.append(await test_config_loading())

    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)

    passed = sum(results)
    total = len(results)

    print(f"\nTests passed: {passed}/{total}")

    if passed == total:
        print("\n[SUCCESS] All tests passed! Your setup is ready.")
        print("\nNext steps:")
        print("1. Configure your email provider credentials in .env")
        print("2. Add your target accounts to config/accounts.py")
        print("3. Run sync_emails.py to start syncing")
    else:
        print("\n[WARNING] Some tests failed. Check the errors above.")
        if not results[0]:
            print("\nMake sure Neo4j is running:")
            print("  cd /Users/champion/graffiti/graphiti && docker compose up neo4j -d")

    return passed == total


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
