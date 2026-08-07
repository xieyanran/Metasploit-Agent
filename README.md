# firstpentestAgent

## Why Agent?

### Why not a workflow?

A workflow performs well when the decision logic can be made fully explicit — every branch reduces to an if/else condition, and the process can be represented as a static flowchart. Penetration testing rarely fits this model. Once a target's fingerprint has been identified, a single service may match several candidate exploit modules, and there is no fixed rule for ranking those candidates or deciding when to abandon a failing approach. Historically, this judgment has relied on the experience and intuition of the pentester rather than a codified procedure — precisely the kind of gap a flowchart cannot capture.

### Why an agent?

An agent is a goal-oriented, autonomous system: it perceives its environment, and an LLM serves as its reasoning core — planning, reasoning over the current state, and invoking tools to pursue the pentest objective. Penetration testing already follows a fairly mature, well-established methodology; the opportunity here is not to reinvent that process, but to let an agent absorb and execute it. By automating the repetitive, low-judgment steps, the agent frees the human operator to focus on the critical decision points, extending the practical reach of the LLM and moving the discipline incrementally toward greater autonomy — improving overall efficiency while preserving the structure that already works.

## Metaspolit

### Preparations
- Install Metasploit elegant: https://docs.metasploit.com/docs/using-metasploit/getting-started/nightly-installers.html

- Start RPC Server
    - Note: 每次重新打开 Metasploit，都需要重新执行, 因为这是一个插件，不会默认一直开启。

    ```
    load msgrpc ServerHost=127.0.0.1 ServerPort=Portnum User=username Pass=password SSL=false
    ```
