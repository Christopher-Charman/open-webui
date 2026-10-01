# Gateway/Tailscale Host Supervision Acceptance — 2026-10-01

Status: HOST-SIDE SUPERVISION ACCEPTED / GATEWAY PRIVATE-NETWORK ATTACHMENT BLOCKED

## Scope

This receipt covers only the existing PowerPC live-runtime Gateway/Tailscale host-side path:

`tailscaled userspace daemon -> persisted Tailscale identity/state -> existing Serve ingress -> management sshd 127.0.0.1:2222`.

It does not claim end-to-end Gateway SSH callability while Gateway has no assigned private network site.

## Preserved invariants

- Runtime identity remains `fasthost.powerpc` / `csh3280350` / UID `2257347` / `hp3-rr-1024747.hostingp3.local`.
- Existing management sshd remains `127.0.0.1:2222`.
- Existing Tailscale node identity remains `powerpc-live`.
- Existing Tailscale IPv4 remains `100.118.16.80`.
- No Tailscale re-authentication was performed.
- No SSH host/client keys were rotated, removed, or re-enrolled.
- No Tailscale Serve mapping was rewritten.
- No Gateway server was deleted/recreated.
- Existing `POWERPC_CONTROL_V1` cron schedule was not changed.

## Root cause

The existing userspace `tailscaled` process had stopped while its state, socket path, PID file, binaries, and management sshd remained present. No independent lifecycle supervisor existed for Tailscale.

A bounded restart against the existing state reached:

- persisted authenticated profile `Christopher-Charman@github`;
- `machineAuthorized=true`;
- `nodeKeyExpired=false`;
- `Hostinfo.IngressEnabled=true`;
- Tailscale state transition `NoState -> Starting -> Running`;
- native address `100.118.16.80`;
- DERP 8 / London connection.

## Supervision repair

Added `bootstrap-relay/gateway-tailscale/tailscale-service` as an idempotent user-level controller.

The existing accepted `powerpc-control-service` watchdog now calls `tailscale-service ensure` while preserving its existing cron lifecycle:

- `@reboot ... powerpc-control ensure ... # POWERPC_CONTROL_V1`
- `* * * * * ... powerpc-control ensure ... # POWERPC_CONTROL_V1`

No new scheduler was created.

Live deployment receipt:

- GitHub Actions run: `36894400648`
- result: `TAILSCALE_SUPERVISION_DEPLOY=PASS`
- PowerPC control after deployment: `RUNNING`
- watchdog cron: `EXISTING_UNCHANGED`

## Delayed verification

Subsequent read-only runs:

- `36894769648`
- `36895060402`
- `36895469768`

Fresh evidence established:

- PID file remains `112218`;
- `kill -0 112218`: PASS;
- `/proc/112218/exe` exactly matches the deployed `tailscaled` binary;
- command line remains `--tun=userspace-networking --state=.../tailscaled.state --socket=.../tailscaled.sock`;
- Tailscale socket remains present;
- watchdog repeatedly reports `TAILSCALE_SERVICE=ALREADY_LIVE PID=112218`;
- watchdog lock is available between invocations;
- management sshd remains reachable locally with banner `SSH-2.0-OpenSSH_7.4`.

The direct local TCP attempt to `100.118.16.80:22` times out. This is not used as a liveness verdict for userspace-networking Tailscale; kernel self-routing to the node's Tailscale address is not the relevant Gateway acceptance path.

## Gateway boundary

Fresh Gateway region enumeration on 2026-10-01 shows:

- `auto.networkSites=[]`
- `united-states.networkSites=[]`
- `europe.networkSites=[]`
- `oceania.networkSites=[]`

Therefore the remaining end-to-end blocker is outside the PowerPC host:

`Gateway private execution plane -> networkSiteId/Tailscale attachment -> 100.118.16.80:22`

No current `networkSiteId` exists to attach `powerpc-live`.

Do not fall back to public Tailscale Funnel for native SSH; the earlier protocol mismatch is already closed.

## Exact frontier

`POWERPC_CONTROL = RUNNING`

`MANAGEMENT_SSHD = LIVE`

`TAILSCALE_DAEMON = LIVE / SUPERVISED / EXISTING IDENTITY PRESERVED`

`TAILSCALE_PRIVATE_NODE = 100.118.16.80 / AUTHORIZED / RUNNING`

`GATEWAY_PRIVATE_NETWORK_SITE = UNAVAILABLE`

`END_TO_END_GATEWAY_SSH = BLOCKED ON networkSiteId AVAILABILITY`

Invariant:

`HOST REPAIR COMPLETE != GATEWAY PRIVATE ROUTING AVAILABLE`

`DO NOT REAUTH TAILSCALE`

`DO NOT ROTATE SSH KEYS`

`DO NOT RECREATE GATEWAY SERVER`

`PRESERVE OWNED CONTROL AND GATEWAY/TAILSCALE IN PARALLEL`
