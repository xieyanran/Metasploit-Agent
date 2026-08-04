from agent.loop import AgentLoop
from llm.openai_client import OpenAIClient

client = OpenAIClient()

agent = AgentLoop(client)

agent.run(
    goal="""
    Exploit vsftpd 2.3.4 on 192.168.56.101
    """
)