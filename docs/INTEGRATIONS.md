# Integrations: ERP and directory

Research notes on connecting the tracking system to an ERP (Infor SyteLine
first, others later) and to a corporate directory (Active Directory).

Status: **research, not implemented.** Details about third-party products
come from public sources listed at the end and must be verified against a
real instance before any connector is built (tasks R-01…R-03 in
[TASKS.md](TASKS.md)).

---

## Where the system sits

In ISA-95 terms — the standard model of manufacturing IT — the system is a
lightweight **level-3 (manufacturing operations)** application between the
machine (level 2) and the ERP (level 4):

| Level | What | Here |
|---|---|---|
| 4 — Business planning | ERP: orders, items, job routings, costing | SyteLine, 1C, others |
| 3 — Manufacturing operations | Execution tracking, production reporting | **This system** |
| 2 — Control | Machine control, NC programs | Punching machine, NCeXpress output |

That position defines the two useful directions of integration:

- **Down from the ERP (plan):** which job orders and operations a shift task
  belongs to, which item each part name is.
- **Up to the ERP (actual):** quantities completed per job operation, by whom
  and when — what the ERP otherwise gets from paper route sheets typed in by
  hand.

---

## The core problem: mapping

Integration is mostly a mapping problem, not a transport problem.

| Our side | ERP side | How to link |
|---|---|---|
| Part name from `PART_NAME` (e.g. a drawing number) | Item | Naming convention, or an admin-maintained mapping table |
| Shift task (content-based ID) | One or more job orders | Not in the NC files: `CUSTOMER` and `Order ID` are empty in the files analysed (ROADMAP item 8). Needs a mapping table, or the order number in the file name / CAM fields |
| Program executed on the punching machine | A job operation (routing step at the punching work centre) | Operation sequence of the punching step in the job's routing |
| Pieces of a part in a completed program | Quantity completed at that operation | Direct, once the part→item and task→job links exist |
| Operator | ERP employee | Mapping table or a shared directory identity (AD) |

Consequences for the design:

- **Mapping tables live on our server** and are edited by the administrator;
  a connector may pre-fill them from the ERP.
- **Unmapped data is never dropped:** production is recorded regardless and
  sent later, once the mapping exists.
- One NC program usually contains parts from **several jobs** (nesting), so
  one "program done" event may turn into several ERP transactions.

---

## Integration patterns

| Pattern | Who calls whom | Direction | Use |
|---|---|---|---|
| **Push through a connector** | We call the ERP | up | Production events are queued in an integration outbox on the server; a connector delivers them with retries and idempotency keys. The ERP being down never blocks the shop floor |
| **Scheduled pull through a connector** | We call the ERP | down | The connector periodically loads jobs, routings, items into local reference tables |
| **Event feed** | The ERP calls us | up | The ERP side runs its own scheduled job that reads new production events from our Integration API by cursor. No write access to the ERP needed on our side — often the easiest route with 1C |
| **Reference push** | The ERP calls us | down | The ERP sends jobs and items to our Integration API when they change |
| **Webhook** | We call any URL | up | Generic HTTP POST of each event with a configurable template — for middleware and low-code tools |
| **File drop (CSV / XML)** | Shared folder | both | Universal fallback: any ERP can import a file. First connector to build — it needs no ERP access to develop |

---

## Integration hub

A server module that connects any number of external systems and is
configured by the administrator in the web panel — no code changes and no
server restart to add, change or disable a connection.

### Parts

| Part | What it does |
|---|---|
| **Connector registry** | Connector types are plugins. Built-in: file drop, webhook, Infor SyteLine, 1C OData. Third parties add their own as a Python package registered under the entry-point group `fpc_server.connectors` — no fork needed |
| **Connection profiles** | An administrator creates a connection from a connector type: name, base URL, authentication, TLS options, timeouts, schedule. Several connections of one type are allowed (e.g. a test and a live ERP) |
| **Settings schema** | Each connector declares its settings as a typed model; the admin form is generated from it, validated on save, and has a **Test connection** button |
| **Secrets** | Passwords, tokens and keys are encrypted at rest with a server master key supplied at deployment (environment variable or Docker secret). They are never shown again after saving and never written to logs |
| **Routing** | Which event types go to which connection (`program_done`, `program_undone`, shift totals, …), with filters by workstation or work centre |
| **Mapping** | Tables for parts → items, tasks → jobs, operators → employees, workstations → work centres. Edited in the panel, imported from CSV, or pre-filled by the connector's pull. An "unmapped" list shows what is waiting |
| **Templates** | For the webhook and file-drop connectors the payload is a template the administrator edits, with a preview on a sample event |
| **Integration outbox** | Every outgoing message is stored first, then delivered: retries with back-off, an idempotency key per message, a dead-letter list after N failures, manual retry |
| **Delivery log** | Each attempt: time, connection, result, response summary (secrets redacted). A status tile per connection: last success, backlog, last error |
| **Integration API** | For systems that call us: scoped API tokens (read production, read reference, write reference); an event feed read by cursor; reference-data upload; webhook subscriptions |

### Connector interface

```
Connector
  settings_model            -> typed settings, used to render the admin form
  test(settings)            -> reachable, authenticated, version
  pull_reference(settings)  -> jobs, operations, items, employees
  push(settings, messages)  -> result per message: ok / retry / reject
```

A connector only translates: it receives already-mapped messages and returns
a result per message. Retries, idempotency, logging and scheduling belong to
the hub, so every connector gets them for free.

### Authentication methods offered to connectors

None, Basic, Bearer token, API key in a header, OAuth 2.0 client credentials,
and the Infor ION API credentials file (`.ionapi`) for SyteLine in the cloud.

---

## Infor SyteLine (CloudSuite Industrial)

### Relevant concepts

- **Jobs** — production orders, with a **routing** of operations (work
  centre, sequence). Paper **job travellers / route sheets** are printed from
  them.
- **Job transactions** — reported quantities (completed, scrapped) and hours
  per job operation. This is where "actual" production lands.
- **Items** — the part master.

### Access options

| Option | What | Fit |
|---|---|---|
| **IDO REST API** (Mongoose `IDORequestService`) | Standard CRUD per Intelligent Data Object: `…/IDORequestService/ido/load/{IDO}`, `…/ido/update/{IDO}`, `…/ido/invoke/{IDO}`; a configuration header `X-Infor-MongooseConfig`; token-based authentication on premises, OAuth 2.0 via the ION API Gateway in the cloud | **Preferred.** Synchronous, well documented, on-premises and cloud |
| **ION + BODs** | Event-driven XML Business Object Documents through Infor ION; public sources mention a job-transaction BOD for operation completions | For sites that already run ION; heavier to set up |
| **SOAP web services** | Older IDO web service | Only if REST is unavailable |
| **Direct SQL** | Reading or writing the SyteLine database | **No.** Bypasses business logic and validation; unsupported |

### IDOs of interest (to verify)

| IDO | Purpose | Direction |
|---|---|---|
| `SLJobs` | Job orders | pull |
| `SLJobRoutes` | Job routing operations | pull |
| `SLItems` | Items | pull |
| `SLJobtrans` | Job transactions: quantity completed or scrapped per operation | push |

An existing commercial MES connector publicly documents writing closed
labour tickets as `SLJobtrans` records, which supports this approach.

### Open points

- **No public sandbox.** SyteLine is licensed; developing against it needs
  access to a customer or partner instance. Until then the connector is
  built against a **mock** that follows the documented API shape (see
  [TEST_BENCH.md](TEST_BENCH.md)).
- Which transaction type the site uses to post punching output: a job
  transaction per operation, or a Factory Track data-collection
  transaction.
- Whether the job number can be carried in the NC file or its name, which
  would remove most of the manual mapping.

---

## Other ERPs

| ERP | Access | Notes |
|---|---|---|
| **1C:Enterprise** (1C:ERP, 1C:UPP) | Standard OData v3 REST interface published per infobase; custom HTTP services | Common in Russia and CIS; OData gives catalogs, documents and registers without custom code |
| **Generic** | File drop, webhook, event feed | Covers anything that can import a file, accept HTTP or call HTTP |

The connector interface stays the same; only the adapter changes.

### 1C in more detail

1C offers two routes, and the hub supports both:

- **We write to 1C through OData.** The administrator publishes the
  standard OData interface of the infobase; our 1C connector reads catalogs
  (items, employees) and creates documents that record production output.
  Which document that is depends on the 1C configuration (for example,
  production stages in 1C:ERP) and must be agreed with the site's 1C team.
- **1C reads from us.** A 1C developer adds a scheduled job on the 1C side
  that calls our Integration API, reads new events by cursor and posts them
  with 1C's own logic. This keeps all 1C business rules inside 1C and needs
  no write access for us — often what a 1C team prefers.

The second route needs nothing 1C-specific on our side: it is the generic
event feed, documented in the API description.

---

## Active Directory

### Why

Shops with a Windows domain do not want a second list of users and
passwords. Supervisors and administrators should sign in with their domain
accounts, and roles should follow domain groups.

### Design

- **Authentication provider interface** on the server: `local` (built-in
  users, from stage 1) and `ldap` (AD). Designed in stage 1, LDAP added in
  stage 7.
- **LDAP over TLS** (LDAPS, port 636, or StartTLS) with a service account
  for look-ups; the user's own credentials verified by a bind. Library:
  `ldap3` (pure Python) on the server.
- **Group → role mapping** configured by the administrator: e.g.
  `CN=MES-Supervisors` → `supervisor`.
- **Operators keep PINs.** A shop-floor PIN is not a domain password. An
  operator record can be *linked* to a domain account for identity, while
  sign-in at the machine stays name + PIN.
- **Optional later:** single sign-on in the browser via Kerberos/SPNEGO.

### Open points

- Whether operators have domain accounts at all.
- Whether user records are provisioned on first sign-in or synchronised on a
  schedule.

---

## Sources

Public sources consulted; verify details against a real instance.

- [Infor docs — LoadCollection, REST API version 2](https://docs.infor.com/csi/2022.x/en-us/csbiolh/mgiiea_cl_sl/dwn1576796415221.html)
- [Infor docs — Mongoose LoadCollection](https://docs.infor.com/mg/latest/en-us/mongooseolh/mgiiea/scb1573247746553.html)
- [Infor Community — What is X-INFOR-MongooseConfig](https://community.infor.com/discussion/446/what-is-x-infor-mongooseconfig)
- [Infor Community — IDO REST API](https://community.infor.com/discussion/19177/ido-rest-api)
- [MachineMetrics — Infor SyteLine cloud connector](https://docs.machinemetrics.com/docs/integrations/erp-connectors/infor-syteline-cloud-connector/)
- [Visual South — SyteLine integration methods](https://www.visualsouth.com/blog/infor-cloudsuite-industrial-integrate-existing-systems)
- [Netray — SyteLine REST API integration](https://www.netray.co/resources/syteline-api-integration-rest)
- [1C Developer Network — REST interface](https://1c-dn.com/1c_enterprise/rest_interface/)
- [1C knowledge base — Publishing standard REST API for your infobase](https://kb.1ci.com/1C_Enterprise_Platform/FAQ/Development/Integration/Publishing_standard_REST_API_for_your_infobase/)
