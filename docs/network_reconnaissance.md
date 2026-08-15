# Network Reconnaissance

## Passive Reconnaissance

### Common Passive Reconnaissance activity includes:

- LinkedIn about job posting or company career pages for tech stack hints

- **Querying WHOIS or RDAP**: the protocol provide registration details for domain names.

- **nslookup and dig**: DNS query tools, querying public DNS records from open resolvers

- reveal unadvertised subdomains: DNSDumpster, https://crt.sh

- Public search engine: Shodan.io



## Active Reconnaissance

### Common Active Reconnaissance activity includes:

- Social engineering attempts (phishing, vishing, pretexting phone calls)

-  Reconnaissance from Web Browser
    - Developer Tools
    - Browser Extensions: Wappalyzer

- Ping

- Traceroute

- Telnet
> Telnet protocol: Communicate with remote system via command-line interface. From a security perspective, telnet sends all data in cleartext, including usernames and passwords. The secure alternative is SSH.
> banner grabing: You connect to a service and read the initial response, called the "banner", that the server sends back. Banners frequently reveal the software name and version running on that port.

- Netcat(simply as nc)
    -  It can function as a client that connects to a listening port, or as a server that listens on a port of your choice. This dual capability makes it useful for banner grabbing, port probing, simple file transfers, and basic client-server communication. 
    - networking utility that supports both TCP and UDP protocols. 





