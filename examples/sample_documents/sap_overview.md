# SAP System Overview — Sample Reference Document

> Convert this file to PDF (e.g. via VS Code → "Export PDF" or Pandoc) to use
> as test input for the `/upload` endpoint.

---

## What is SAP?

SAP (Systems, Applications & Products in Data Processing) is the world's leading
enterprise resource planning (ERP) software, used by over 440,000 companies in
more than 180 countries. SAP integrates core business functions — finance,
logistics, HR, and manufacturing — into a single, real-time system.

SAP S/4HANA is the latest generation, built on the in-memory HANA database,
replacing SAP ECC (ERP Central Component). S/4HANA delivers simplified data
models, embedded analytics, and a modern Fiori user interface.

---

## Core SAP Modules

### SAP FI — Financial Accounting
SAP FI manages an organisation's financial transactions in real time. It
produces statutory financial statements and provides a complete audit trail.

Key sub-modules:
- **FI-GL** – General Ledger: central repository of all accounting entries.
- **FI-AR** – Accounts Receivable: manages customer invoices and payments.
- **FI-AP** – Accounts Payable: manages vendor invoices and outgoing payments.
- **FI-AA** – Asset Accounting: tracks fixed assets throughout their lifecycle.
- **FI-BL** – Bank Ledger: handles bank statements and cash management.

Important transaction codes: FB01 (post document), FB50 (G/L account posting),
F-02 (enter G/L account posting), FS00 (G/L account master record).

### SAP CO — Controlling
SAP CO supports internal management accounting by tracking costs and revenues.
It works hand-in-hand with FI through the FICO integration.

Key sub-modules:
- **CO-CCA** – Cost Centre Accounting: collects costs by responsibility area.
- **CO-PA**  – Profitability Analysis: analyses profitability by market segment.
- **CO-PC**  – Product Cost Controlling: calculates costs for manufactured goods.
- **CO-OM**  – Overhead Management: allocates overhead costs to cost objects.

### SAP MM — Materials Management
SAP MM covers the entire procurement and inventory management process,
from purchase requisition through goods receipt to invoice verification.

Key sub-modules:
- **MM-PUR** – Purchasing: manages RFQs, purchase orders, and contracts.
- **MM-IM**  – Inventory Management: goods receipts, transfers, and stock counts.
- **MM-WM**  – Warehouse Management: detailed warehouse structure and movements.
- **MM-IV**  – Invoice Verification (Logistics Invoice Verification): 3-way match
  of PO, goods receipt, and vendor invoice.
- **MM-CBP** – Consumption-Based Planning: MRP for replenishment of stock items.

Core transaction codes: ME21N (create PO), MIGO (goods movement), MIRO (invoice
verification), ME51N (purchase requisition), MB52 (warehouse stocks).

The standard procurement cycle in MM:
1. Purchase Requisition (PR) created by department or MRP.
2. PR converted to Request for Quotation (RFQ) — transaction ME41.
3. Quotations evaluated and Purchase Order (PO) raised — ME21N.
4. Goods Receipt posted against PO — MIGO, movement type 101.
5. Invoice received and matched against PO and GR — MIRO.
6. Payment processed via FI-AP.

### SAP SD — Sales & Distribution
SAP SD manages the order-to-cash process, from customer inquiry to billing
and delivery. SD is tightly integrated with MM (for availability checks and
goods issue) and FI (for billing and revenue posting).

Key sub-modules:
- **SD-SLS** – Sales: quotations, sales orders, contracts.
- **SD-SHP** – Shipping: delivery creation, packing, goods issue.
- **SD-BIL** – Billing: invoice generation, credit/debit memos.
- **SD-CAS** – Sales Support: activity tracking, mailing lists.

Order-to-cash cycle in SD:
1. Inquiry → Quotation (VA21, VA11).
2. Sales Order creation — VA01.
3. Availability Check and Credit Check.
4. Delivery creation — VL01N; Picking and Packing.
5. Goods Issue posted — reduces inventory in MM.
6. Billing document created — VF01; transfers revenue to FI.
7. Customer payment applied in FI-AR.

### SAP PP — Production Planning
SAP PP manages manufacturing processes, from demand planning and MRP through
production order execution and confirmation.

Sub-modules include PP-MRP (Material Requirements Planning), PP-SFC (Shop
Floor Control), and PP-PI (Process Industries).

Key transaction codes: MD01 (run MRP), CO01 (create production order),
CO11N (production order confirmation), COOIS (production order information system).

### SAP HCM — Human Capital Management
SAP HCM (also called SAP HR) covers the entire employee lifecycle: recruitment,
organisational management, time management, payroll, and personnel development.

Sub-modules:
- **PA** – Personnel Administration: employee master data.
- **OM** – Organisational Management: org chart and reporting lines.
- **TM** – Time Management: time recording and absence tracking.
- **PY** – Payroll: gross-to-net payroll calculation by country.
- **LD** – Learning & Development: training catalogue and completion tracking.

---

## SAP S/4HANA vs SAP ECC

| Feature              | SAP ECC 6.0          | SAP S/4HANA            |
|----------------------|----------------------|------------------------|
| Database             | Any (Oracle, MSSQL…) | SAP HANA only          |
| Data model           | Aggregated tables    | Simplified (ACDOCA)    |
| User interface       | SAP GUI / Web Dynpro | SAP Fiori (responsive) |
| Real-time analytics  | Limited (BW separate)| Embedded analytics     |
| Deployment           | On-premise           | On-premise, Cloud, PCE |
| Maintenance end      | 2027 (extended 2030) | Current strategic path |

The key table changes in S/4HANA Finance: BSEG, BKPF, BSET, BSAS, BSAK, BSAD,
BSIS, BSID, BSAS are replaced by the Universal Journal table **ACDOCA**, which
stores all FI and CO postings in a single, non-aggregated line-item table.

---

## SAP Integration Architecture

SAP systems communicate using:
- **RFC (Remote Function Call)** — synchronous function-module invocation.
- **IDocs (Intermediate Documents)** — asynchronous document exchange format.
- **BAPIs (Business Application Programming Interfaces)** — stable RFC APIs.
- **SAP PI/PO (Process Integration / Process Orchestration)** — middleware hub.
- **SAP Integration Suite** (Cloud Integration, API Management) — modern iPaaS.

---

## Common SAP Basis Concepts

- **SAP Basis** is the technical foundation: system administration, transports,
  user management, and performance tuning.
- **ABAP** (Advanced Business Application Programming) is SAP's proprietary
  4GL language used for custom development and enhancements.
- **Transport Management System (TMS)** moves configuration and code between
  Development → Quality → Production landscapes.
- **Solution Manager (SolMan)** provides centralised ALM, monitoring, and
  ITSM capabilities across the SAP landscape.
