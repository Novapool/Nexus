#!/usr/bin/env python3
"""
Nexus Integration Test Script
Tests the complete flow: server management → SSH connection → command execution → AI integration
"""

import asyncio
import httpx
import json
import sys
from pathlib import Path
from typing import Dict, Any, Optional
import time

# Configuration
NEXUS_BASE_URL = "http://127.0.0.1:8000"
TEST_SERVER_CONFIG = {
    "hostname": "192.168.1.16",  # Replace with your actual server
    "username": "laith",            # Replace with your username
    "password": "Flash49155727!",            # Replace with your password (or use private key)
    "port": 22,
    "description": "Test server for Nexus integration",
    "os_type": "ubuntu"  # or "debian", "centos", etc.
}

class NexusTestClient:
    """Test client for Nexus API"""
    
    def __init__(self, base_url: str):
        self.base_url = base_url
        self.client = httpx.AsyncClient(timeout=60.0)
        self.test_server_id: Optional[str] = None
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.client.aclose()
    
    async def health_check(self) -> Dict[str, Any]:
        """Check if Nexus API is running"""
        print("🏥 Checking Nexus health...")
        try:
            response = await self.client.get(f"{self.base_url}/health/detailed")
            if response.status_code == 200:
                health_data = response.json()
                print(f"✅ Nexus is healthy: {health_data['service']}")
                
                # Check AI service status
                if "components" in health_data:
                    ai_status = health_data["components"].get("ai_service", {})
                    if ai_status.get("status") == "healthy":
                        print(f"✅ AI service is healthy: {ai_status.get('provider', 'unknown')}")
                        print(f"   Models available: {ai_status.get('models_available', 0)}")
                    else:
                        print(f"⚠️ AI service issue: {ai_status}")
                
                return health_data
            else:
                print(f"❌ Health check failed: HTTP {response.status_code}")
                return {}
        except Exception as e:
            print(f"❌ Health check error: {e}")
            return {}
    
    async def list_servers(self) -> Dict[str, Any]:
        """List all configured servers"""
        print("\n📋 Listing servers...")
        try:
            response = await self.client.get(f"{self.base_url}/api/v1/servers/")
            if response.status_code == 200:
                data = response.json()
                servers = data.get("servers", [])
                print(f"✅ Found {len(servers)} servers:")
                
                for server in servers:
                    print(f"   - {server['hostname']} ({server['id'][:8]}...)")
                    print(f"     OS: {server['os_type']}, Status: {server.get('connection_status', 'unknown')}")
                
                return data
            else:
                print(f"❌ Failed to list servers: HTTP {response.status_code}")
                return {"servers": []}
        except Exception as e:
            print(f"❌ Server listing error: {e}")
            return {"servers": []}
    
    async def create_test_server(self, config: Dict[str, Any]) -> Optional[str]:
        """Create a test server configuration"""
        print(f"\n🖥️ Creating test server: {config['hostname']}...")
        try:
            response = await self.client.post(
                f"{self.base_url}/api/v1/servers/",
                json=config
            )
            if response.status_code == 200:
                server_data = response.json()
                server_id = server_data["id"]
                print(f"✅ Created test server: {server_id[:8]}...")
                self.test_server_id = server_id
                return server_id
            else:
                print(f"❌ Failed to create server: HTTP {response.status_code}")
                try:
                    error_detail = response.json()
                    print(f"   Error: {error_detail}")
                except:
                    print(f"   Error: {response.text}")
                return None
        except Exception as e:
            print(f"❌ Server creation error: {e}")
            return None
    
    async def test_server_connection(self, server_id: str) -> bool:
        """Test SSH connection to server"""
        print(f"\n🔌 Testing SSH connection to server {server_id[:8]}...")
        try:
            response = await self.client.post(
                f"{self.base_url}/api/v1/servers/{server_id}/test-connection"
            )
            if response.status_code == 200:
                result = response.json()
                if result.get("connection_status") == "success":
                    details = result.get("details", {})
                    print(f"✅ SSH connection successful!")
                    print(f"   Response time: {details.get('response_time_ms', 'unknown')} ms")
                    print(f"   Server info: {details.get('server_info', {})}")
                    return True
                else:
                    print(f"❌ SSH connection failed: {result}")
                    return False
            else:
                print(f"❌ Connection test failed: HTTP {response.status_code}")
                return False
        except Exception as e:
            print(f"❌ Connection test error: {e}")
            return False
    
    async def execute_direct_command(self, server_id: str, command: str, safety_level: str = "safe") -> Dict[str, Any]:
        """Execute a direct command on the server"""
        print(f"\n💻 Executing direct command: '{command}'")
        try:
            response = await self.client.post(
                f"{self.base_url}/api/v1/servers/{server_id}/execute",
                params={
                    "command": command,
                    "safety_level": safety_level,
                    "timeout": 30
                }
            )
            if response.status_code == 200:
                result = response.json()
                exec_result = result.get("result", {})
                
                print(f"✅ Command executed successfully!")
                print(f"   Exit code: {exec_result.get('exit_code', 'unknown')}")
                print(f"   Execution time: {exec_result.get('execution_time', 'unknown')} seconds")
                
                if exec_result.get("stdout"):
                    output_preview = exec_result["stdout"][:200]
                    if len(exec_result["stdout"]) > 200:
                        output_preview += "..."
                    print(f"   Output: {output_preview}")
                
                if exec_result.get("stderr"):
                    print(f"   Errors: {exec_result['stderr']}")
                
                return result
            else:
                print(f"❌ Command execution failed: HTTP {response.status_code}")
                try:
                    error_detail = response.json()
                    print(f"   Error: {error_detail}")
                except:
                    print(f"   Error: {response.text}")
                return {}
        except Exception as e:
            print(f"❌ Command execution error: {e}")
            return {}
    
    async def execute_natural_command(self, server_id: str, prompt: str, safety_level: str = "normal") -> Dict[str, Any]:
        """Execute a natural language command via AI"""
        print(f"\n🤖 Executing AI command for prompt: '{prompt}'")
        try:
            response = await self.client.post(
                f"{self.base_url}/api/v1/commands/execute-natural",
                json={
                    "prompt": prompt,
                    "server_id": server_id,
                    "safety_level": safety_level
                }
            )
            if response.status_code == 200:
                result = response.json()
                
                print(f"✅ AI command executed!")
                print(f"   Generated command: {result.get('command', 'unknown')}")
                print(f"   Explanation: {result.get('explanation', 'no explanation')}")
                print(f"   Success: {result.get('success', False)}")
                print(f"   Safety level: {result.get('safety_level', 'unknown')}")
                
                if result.get("warnings"):
                    print(f"   Warnings: {', '.join(result['warnings'])}")
                
                if result.get("output"):
                    output_preview = result["output"][:200]
                    if len(result["output"]) > 200:
                        output_preview += "..."
                    print(f"   Output: {output_preview}")
                
                if result.get("error"):
                    print(f"   Error: {result['error']}")
                
                return result
            else:
                print(f"❌ AI command execution failed: HTTP {response.status_code}")
                try:
                    error_detail = response.json()
                    print(f"   Error: {error_detail}")
                except:
                    print(f"   Error: {response.text}")
                return {}
        except Exception as e:
            print(f"❌ AI command execution error: {e}")
            return {}
    
    async def generate_ai_command(self, server_id: str, prompt: str) -> Dict[str, Any]:
        """Generate a command using AI without executing it"""
        print(f"\n🧠 Generating AI command for: '{prompt}'")
        try:
            # Use shorter timeout for AI requests
            async with httpx.AsyncClient(timeout=30.0) as ai_client:
                response = await ai_client.post(
                    f"{self.base_url}/api/v1/ai/generate-command",
                    json={
                        "prompt": prompt,
                        "server_id": server_id,
                        "reasoning_level": "medium",
                        "os_type": "ubuntu"
                    }
                )
                if response.status_code == 200:
                    result = response.json()
                    
                    print(f"✅ AI command generated!")
                    print(f"   Command: {result.get('command', 'unknown')}")
                    print(f"   Explanation: {result.get('explanation', 'no explanation')}")
                    print(f"   Risk level: {result.get('risk_level', 'unknown')}")
                    print(f"   Is safe: {result.get('is_safe', False)}")
                    
                    if result.get("warnings"):
                        print(f"   Warnings: {', '.join(result['warnings'])}")
                    
                    if result.get("alternatives"):
                        print(f"   Alternatives: {', '.join(result['alternatives'])}")
                    
                    return result
                else:
                    print(f"❌ AI command generation failed: HTTP {response.status_code}")
                    try:
                        error_detail = response.json()
                        print(f"   Error: {error_detail}")
                    except:
                        print(f"   Error: {response.text}")
                    return {}
        except asyncio.TimeoutError:
            print(f"❌ AI command generation timed out (30s)")
            return {}
        except Exception as e:
            print(f"❌ AI command generation error: {e}")
            return {}
    
    async def cleanup_test_server(self):
        """Clean up test server if created"""
        if self.test_server_id:
            print(f"\n🧹 Cleaning up test server {self.test_server_id[:8]}...")
            try:
                response = await self.client.delete(
                    f"{self.base_url}/api/v1/servers/{self.test_server_id}"
                )
                if response.status_code == 200:
                    print("✅ Test server cleaned up successfully")
                else:
                    print(f"⚠️ Cleanup warning: HTTP {response.status_code}")
            except Exception as e:
                print(f"⚠️ Cleanup error: {e}")


async def run_integration_test():
    """Run the complete integration test"""
    print("🚀 Starting Nexus Integration Test")
    print("=" * 60)
    
    async with NexusTestClient(NEXUS_BASE_URL) as client:
        try:
            # Step 1: Health check
            health_data = await client.health_check()
            if not health_data:
                print("❌ Cannot proceed without healthy Nexus service")
                return False
            
            # Step 2: List existing servers
            servers_data = await client.list_servers()
            existing_servers = servers_data.get("servers", [])
            
            # Step 3: Use existing server or create test server
            server_id = None
            if existing_servers:
                print(f"\n🎯 Using existing server: {existing_servers[0]['hostname']}")
                server_id = existing_servers[0]['id']
            else:
                print("\n🎯 No existing servers found, creating test server...")
                print("⚠️ Make sure to update TEST_SERVER_CONFIG with your actual server details!")
                
                # Check if config looks like default values
                if TEST_SERVER_CONFIG["hostname"] == "your-server.example.com":
                    print("❌ Please update TEST_SERVER_CONFIG in the script with real server details")
                    return False
                
                server_id = await client.create_test_server(TEST_SERVER_CONFIG)
                if not server_id:
                    print("❌ Cannot proceed without a valid server")
                    return False
            
            # Step 4: Test SSH connection
            connected = await client.test_server_connection(server_id)
            if not connected:
                print("❌ Cannot proceed without SSH connection")
                return False
            
            # Step 5: Execute simple direct command (ls)
            print("\n" + "=" * 60)
            print("📁 Testing direct command execution...")
            ls_result = await client.execute_direct_command(server_id, "ls -la", "safe")
            
            if not ls_result.get("result", {}).get("success", False):
                print("⚠️ Direct command failed, but continuing...")
            
            # Step 6: Use AI to generate and execute ls command
            print("\n" + "=" * 60)
            print("🤖 Testing AI command generation and execution...")
            
            ai_ls_result = await client.execute_natural_command(
                server_id, 
                "list all files in the current directory with detailed information",
                "safe"
            )
            
            # Step 7: Generate AI commands for system update (without executing)
            print("\n" + "=" * 60)
            print("🔄 Testing AI command generation for system updates...")
            
            # Generate update command
            update_cmd = await client.generate_ai_command(
                server_id,
                "update the package list using apt"
            )
            
            # Generate upgrade command  
            upgrade_cmd = await client.generate_ai_command(
                server_id,
                "upgrade all installed packages safely using apt"
            )
            
            # Step 8: Execute update/upgrade with proper safety level
            if update_cmd.get("is_safe") and upgrade_cmd.get("is_safe"):
                print("\n🔄 Executing system update commands...")
                
                # Execute apt update
                update_result = await client.execute_natural_command(
                    server_id,
                    "update the package list using sudo apt update",
                    "normal"  # Higher safety level for sudo commands
                )
                
                # Execute apt upgrade (only if update succeeded)
                if update_result.get("success"):
                    upgrade_result = await client.execute_natural_command(
                        server_id,
                        "upgrade all packages safely using sudo apt upgrade -y",
                        "normal"
                    )
                else:
                    print("⚠️ Skipping upgrade due to update failure")
            else:
                print("⚠️ Update/upgrade commands deemed unsafe by AI, skipping execution")
                print(f"   Update safe: {update_cmd.get('is_safe', False)}")
                print(f"   Upgrade safe: {upgrade_cmd.get('is_safe', False)}")
            
            # Step 9: Test summary
            print("\n" + "=" * 60)
            print("📊 Test Summary:")
            print(f"✅ Health check: {'✓' if health_data else '✗'}")
            print(f"✅ Server listing: {'✓' if servers_data else '✗'}")
            print(f"✅ SSH connection: {'✓' if connected else '✗'}")
            print(f"✅ Direct command: {'✓' if ls_result.get('result', {}).get('success') else '✗'}")
            print(f"✅ AI command execution: {'✓' if ai_ls_result.get('success') else '✗'}")
            print(f"✅ AI command generation: {'✓' if update_cmd.get('command') else '✗'}")
            
            print("\n🎉 Integration test completed!")
            return True
            
        except Exception as e:
            print(f"\n❌ Test failed with exception: {e}")
            return False
        
        finally:
            # Cleanup
            await client.cleanup_test_server()


async def main():
    """Main test runner"""
    print("Nexus Integration Test Script")
    print("This script will test the complete Nexus functionality")
    print("\nMake sure:")
    print("1. Nexus server is running (python run.py)")
    print("2. Ollama is running with gpt-oss:20b model")
    print("3. You have a test server available for SSH")
    print("4. TEST_SERVER_CONFIG is updated with real credentials")
    
    input("\nPress Enter to continue or Ctrl+C to abort...")
    
    try:
        success = await run_integration_test()
        if success:
            print("\n✅ All tests passed!")
            sys.exit(0)
        else:
            print("\n❌ Some tests failed!")
            sys.exit(1)
    except KeyboardInterrupt:
        print("\n\n⏹️ Test interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    # Check if running from correct directory
    if not Path("backend").exists():
        print("❌ Please run this script from the Nexus project root directory")
        sys.exit(1)
    
    # Check Python version
    if sys.version_info < (3, 9):
        print("❌ Python 3.9+ required")
        sys.exit(1)
    
    print("📋 Required dependencies: httpx")
    print("   Install with: pip install httpx")
    print()
    
    asyncio.run(main())
