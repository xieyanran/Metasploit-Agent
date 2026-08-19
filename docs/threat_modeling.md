# Threat Model

> The core is to answer 4 general questions
> What are we working on? Decompose the system into its components, data flows, and boundaries. Understand the architecture before you attack it.

## Foundation Scope: Assets, Data Flows, and Trust Boundaries

-  **Asset** is anything of value that an attacker might target or that the organization needs to protect
    - Data Asset: the information the system stores, process or transmits. Data assets are often the primary target, they are what attackers monetize.
    - System Asset: the infrastructure components that host and move data. edg. Servers, databases, APIs, network devices, and cloud services. Compromising a system asset is often a means to reach a data asset, not an end in itself.
    - Business process assets: The workflows and operations that generate revenue or maintain compliance.

- **Date Flow Diagrams**: DFD is a visual representation of how data moves
    - External Entity: A user, system, or service that outside your control
    - Process: 
    - Data Store: 
    - Data Flow: 
    - Trust Boundary: 

> trust boundaries on a DFD are your initial target list

> **Attack Surface**: The attack surface of a system is the total set of points where an unauthorized user can attempt to enter data, extract data, or interact with the system.Every external entity's connection to an internal process; Every data flow that crosses a trust boundary; Every exposed service or endpoint that accepts input

## Threat Model framework

### Threat Modeling with ATT&CK: The CTID Methodology

1. Search by Industry
2. Search by Platform
3. Compile Navigator Layers
4. Overlay and Analyze
5. Map Defenses to Gaps

- ATT&CK Navigator




