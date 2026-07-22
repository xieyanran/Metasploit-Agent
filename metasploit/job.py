# Business API
# Reference https://docs.rapid7.com/metasploit/standard-api-methods-reference

from metasploit.rpc import MetasploitRPCClient
class JobAPI:
    def __init__(self, rpc: MetasploitRPCClient):
        self.rpc_client = rpc
    
    def list(self) -> dict:
        """
        List all jobs in the Metasploit framework.
        [ "job.list", "<token>"]
        """
        return self.rpc_client.call("job.list")
    
    def info(self, job_id) -> dict:
        """
        Get information about a specific job in the Metasploit framework.
        [ "job.info", "<token>", "<JobID>"]
        """
        return self.rpc_client.call("job.info", job_id)
    
    def stop(self, job_id) -> dict:
        """
        Stop a specific job in the Metasploit framework.
        [ "job.stop", "<token>", "<JobID>"]
        """
        return self.rpc_client.call("job.stop", job_id)