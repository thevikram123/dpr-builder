---
name: extract_dpr
description: "Use this skill when asked to extract structured data, tables, specifications, BOQ items, or numerical information from a government DPR, RFP, or tender document or section. Triggers: 'extract this', 'convert to JSON', 'get the specs', 'extract BOQ', 'pull out the data', 'what tables are in this', 'map this document', 'structured extraction'. Always runs Phase 1 (exploration) before Phase 2 (extraction). Output is a DocumentMap followed by an array of ExtractionResult objects. Do NOT use for summarisation, compliance checking, or prose rewriting."
---

# DPR / RFP Structured Extraction Skill

## Core Philosophy

This skill runs in **two mandatory phases**. Never skip Phase 1.

**Phase 1 — Explore:** Read the full input. Map what exists. Understand the hierarchy. Identify every table and structured section. Report back before extracting anything.

**Phase 2 — Extract:** Based on the map from Phase 1, extract each identified table as a separate clean JSON object with a fully invented schema.

The reason for two phases: government DPRs have deeply nested structures where a table's meaning depends entirely on its parent section. A "Technical Specifications" table under `Component 2 > CCTV > Fixed Box Camera` is completely different from one under `Component 4 > Control Room > Workstations`, even if the columns look similar. Schema and table naming must reflect the hierarchy. This cannot be done correctly without reading the structure first.

---

## Phase 1 — Document Exploration

### When to run Phase 1

Always. Even if the user pastes a single isolated table. Read the surrounding context and heading ancestry before touching any data.

### Phase 1 Output — DocumentMap

Output this in two parts: prose summary first, then structured JSON.

**Prose summary:**

```
## Document Map

**Document:** [filename or "Pasted content"]
**Detected structure:** [one sentence describing the overall document type and structure]

### Hierarchy
[Reproduce the full heading structure as a nested list — every # ## ### #### found]

### Extractable Sections
[One line per extractable section: section_path | content_type | estimated rows]

### Sections to Skip
[One line per skipped section: section_path | reason]

### Cross-cutting Patterns
[Any patterns you notice across sections — e.g. "same compliance table schema repeats
across all 6 camera types", "every component ends with a BOQ table"]
```

**JSON DocumentMap:**

```json
{
  "document_name": "filename or null",
  "total_sections_found": 0,
  "extractable_count": 0,
  "skip_count": 0,
  "components": [
    {
      "component_id": "Component 2",
      "component_name": "Full component name from heading",
      "sections": [
        {
          "section_path": "Component 2 > 2.3 Technical Specifications > 2.3.1 Fixed Box Camera",
          "heading_depth": 3,
          "content_type": "spec_compliance_table",
          "table_count": 1,
          "estimated_rows": 8,
          "extraction_priority": "high",
          "notes": "Compliance and deviation columns are blank — extract as null, do not omit"
        }
      ]
    }
  ],
  "cross_cutting_patterns": [
    "Same 5-column compliance pattern repeats across all camera spec sections",
    "Each component ends with a BOQ table"
  ]
}
```

### `content_type` values — use exactly one

| Value | Description |
|---|---|
| `spec_compliance_table` | Sr.No \| Parameter \| Min Requirement \| Compliance \| Deviation |
| `boq_table` | Sr.No \| Description \| Unit \| Quantity \| Rate \| Amount |
| `equipment_list` | Make/Model \| Quantity \| Specification |
| `sla_table` | Event \| Response Time \| Resolution Time \| Penalty |
| `milestone_table` | Milestone \| Date \| Payment % |
| `eligibility_criteria` | Criterion \| Requirement \| Document Required |
| `reference_standards` | Standard Code \| Description \| Applicability |
| `mixed_table` | Table with columns outside the above patterns |
| `prose_with_params` | No markdown table but contains measurable parameters in prose/bullets |
| `pure_prose` | No structured data — skip in Phase 2 |

### How to build `section_path`

Always trace the full heading ancestry from the top of the document:

```
[Top heading] > [Sub-heading] > [Sub-sub-heading]
```

Real examples from a safe city RFP:
```
Component 2: CCTV > 2.3 Technical Specifications > 2.3.1 Fixed Box Camera
Component 2: CCTV > 2.3 Technical Specifications > 2.3.2 PTZ Camera
Component 3: Control Room > 3.2 Equipment > 3.2.1 Video Wall
Component 3: Control Room > 3.4 BOQ
Annexure A > Approved Makes and Models
```

The section path is the single most important piece of metadata. Everything downstream depends on it.

---

## Phase 2 — Extraction

### When to run Phase 2

Immediately after Phase 1 for small inputs (≤20 extractable sections). For large inputs, ask first:

> "Found [N] extractable sections across [M] components. Extract all, or specific components only?"

### Extraction order

Follow document order — extract sections as they appear, top to bottom. This matches the document's logical flow and makes auditing easier.

### Announcing each extraction

Before each JSON block, output a one-line header using the **exact same `section_path` string** that appears in the JSON:

```
### Extracting: [section_path]
```

**The header and the JSON `section_path` must be identical character for character.** Do not abbreviate, truncate, or rephrase the header. The conversion script may use the header as a human-readable label — if it differs from the JSON, it causes confusion during audits.

Wrong:
```
### Extracting: Component 1 > 4.6. Video Walls and Controllers
```
```json
{ "section_path": "Component 1 > 4.6. IT Equipment in CCC and Seating Area > Video Walls and Controllers" }
```

Correct:
```
### Extracting: Component 1 > 4.6. IT Equipment in CCC and Seating Area > Video Walls and Controllers
```
```json
{ "section_path": "Component 1 > 4.6. IT Equipment in CCC and Seating Area > Video Walls and Controllers" }
```

### ExtractionResult JSON — one object per table

```json
{
  "section_path": "Component 2 > 2.3 Technical Specifications > 2.3.1 Fixed Box Camera",
  "heading_depth": 3,
  "parent_component": "Component 2: CCTV Based Surveillance System",
  "content_type": "spec_compliance_table",
  "should_extract": true,
  "skip_reason": null,
  "table_name": "component2_fixed_box_camera_spec",
  "physical_table_name": "component2_fixed_box_camera_spec",
  "schema_version": 1,
  "rationale": "One sentence: what this table contains and why it is worth extracting",
  "fields": [
    {
      "name": "snake_case_field_name",
      "type": "str | int | float | bool",
      "sql_type": "TEXT | INTEGER | REAL | BOOLEAN",
      "description": "what this field contains",
      "nullable": true,
      "is_primary_key": false,
      "unit": "Nos. | days | Mbps | W | m | years | % | null",
      "source_label": "Verbatim original column header"
    }
  ],
  "row_count": 0,
  "source_row_count": 0,
  "rows": [
    {
      "field_name": "value",
      "another_field": null,
      "req_type": "atomic | multi_condition | standards_list | bullet_list | prose",
      "req_value": "extracted atomic value or null"
    }
  ]
}
```

**New fields explained — all exist to make SQLite conversion deterministic:**

`physical_table_name` — the safe SQL identifier. Copy from `table_name` initially. The conversion script will append a schema hash suffix here; the LLM sets the human-readable base. Must be lowercase snake_case, no SQL reserved words, max 60 chars.

`schema_version` — always `1` on first extraction. The conversion pipeline increments this if the same table is re-extracted with different fields. Allows the pipeline to detect schema drift across document versions without comparing field arrays.

`fields[].sql_type` — explicit SQLite column type. The mapping is fixed:
- `str` → `TEXT`
- `int` → `INTEGER`
- `float` → `REAL`
- `bool` → `INTEGER` (SQLite has no native boolean; 0/1)

Always set this. The conversion script uses it directly for `CREATE TABLE` DDL — no inference needed.

`fields[].is_primary_key` — `true` only for `sr_no` when it is unique across all rows in this table (i.e. no repeated sr_no values and no null sr_no values). `false` for everything else. BOQ tables with continuation rows have `is_primary_key: false` on `sr_no` because the original source has blank sr_no cells. Spec tables with alphanumeric codes like `VBC.001` have `is_primary_key: true` on `sr_no` when codes are unique.

`row_count` — the number of rows in your `rows` array. Fill this after building the rows list. The conversion script uses this to verify insert completeness.

`source_row_count` — the number of data rows visible in the source markdown table (excluding header and separator rows). Must equal `row_count` unless continuation rows were merged (in which case `source_row_count` > `row_count` and the difference equals the number of merged continuation rows). The conversion script logs a warning if `row_count` > `source_row_count`.

`rows[].req_type` and `rows[].req_value` — **two additional columns automatically added to every row of every spec compliance table** (`content_type: "spec_compliance_table"`). These make the `minimum_requirement` field queryable rather than just a text blob. They are NOT added to BOQ tables, equipment lists, or other content types — only spec compliance tables.

`req_type` classifies the structure of the requirement text. Use exactly one of these values:

| `req_type` | Meaning | Example |
|---|---|---|
| `atomic` | Single measurable value — one number, one standard, one yes/no | `"IP66 minimum"`, `"30x"`, `"25 fps"` |
| `multi_condition` | Multiple distinct conditions in one cell, separated by commas or semicolons | `"Colour- 0.01 Lux, B/W - 0.004lux; 0Lux with IR ON"` |
| `standards_list` | Enumeration of standard codes or protocol names | `"ONVIF Profile S, Profile G, Profile T, Profile M"` |
| `bullet_list` | Requirements presented as bullet points (`•`, `-`, `*`) within the cell | `"• Controlling access\n• Secure multi-tenancy\n• Encryption"` |
| `prose` | Dense narrative paragraph — multiple embedded specs that cannot be cleanly atomised | `"Fourth-generation Intel Xeon Scalable processor. Server should be dual processors; support up to 40 cores..."` |

`req_value` extracts the core measurable value when `req_type` is `atomic`. For all other types, set `req_value: null` — do not attempt to parse prose, lists, or multi-condition cells.

Rules for `req_value` when `req_type = "atomic"`:
- Strip qualifiers like "minimum", "maximum", "or better", "or higher", "compliant" — extract the value itself
- `"IP66 minimum"` → `"IP66"`
- `"30x"` → `"30x"`
- `"25 fps at full resolution"` → `"25"`
- `"≥ 95 %"` → `"95"`
- `"1920x1080"` → `"1920x1080"`
- `"Up to Three (3) streams"` — this is a limit, not a single value — set `req_type: "multi_condition"`, `req_value: null`
- When in doubt whether a value is truly atomic, set `req_type: "prose"` and `req_value: null` — do not guess

The conversion script stores `req_type` as `TEXT` and `req_value` as `TEXT` in every spec compliance table. Downstream agents can then query `WHERE req_type = 'atomic'` to find all directly comparable specifications, and use `req_value` for structured comparisons across documents.

When `should_extract` is false:

```json
{
  "section_path": "Component 2 > 2.1 Scope",
  "heading_depth": 2,
  "parent_component": "Component 2: CCTV Based Surveillance System",
  "content_type": "pure_prose",
  "should_extract": false,
  "skip_reason": "Narrative scope description — no tables or quantified parameters",
  "table_name": null,
  "physical_table_name": null,
  "schema_version": null,
  "rationale": null,
  "fields": null,
  "row_count": null,
  "source_row_count": null,
  "rows": null
}
```

### Closing summary

After all sections are processed, output:

```
## Extraction Complete
Extracted: N tables | Skipped: M sections | Total rows: R
```

Then immediately output the `SchemaManifest` JSON block (see SchemaManifest section below).

---

## Table Separation Rules

These rules define when two tables are separate ExtractionResult objects vs the same one.

### Always separate

- Different `section_path` — even if columns are identical
- Different `content_type` — a spec table and a BOQ in the same section are two objects
- Different `parent_component` — tables from Component 2 and Component 3 are always separate

### May share the same schema shape but are still separate objects

Two `spec_compliance_table` entries across `component2_fixed_box_camera_spec` and `component2_ptz_camera_spec` will have identical `fields` — but they are always two separate ExtractionResult objects. The `section_path` carries the distinction. Never merge them.

### Exception — continuation fragments

If LlamaParse has split one logical table across multiple heading sections due to a page break, and the continuation section has no new heading (just rows continuing from the previous section), treat them as one table. Note this in `rationale`.

---

## Table Naming Rules

### Formula

```
{component_prefix}_{content_descriptor}_{qualifier_if_needed}
```

| Good | Bad |
|---|---|
| `component2_fixed_box_camera_spec` | `camera_spec` |
| `component2_ptz_camera_spec` | `specifications` |
| `component3_control_room_boq` | `boq` |
| `component4_network_switch_spec` | `component_4` |
| `annexure_a_approved_makes` | `table_1` |
| `sla_cctv_response_times` | `sla` |

### Rules
- snake_case, lowercase, underscores only
- Always prefix with component or section context
- Specific enough that no two tables in the document can share the same name
- Maximum 60 characters
- SQL reserved words (`order`, `group`, `select`, `where`, `index`, `values`, `table`) must be prefixed: `tbl_order` not `order`

---

## Field Rules

### `fields[].name`
- snake_case English only — never `col_a`, `field_1`, `column_3`
- Capture ALL columns present — do not collapse or drop any
- Distinguish similar columns: `response_time_hrs` vs `resolution_time_hrs`, `min_requirement` vs `max_requirement`

### `fields[].type` and `fields[].sql_type`

Always set both. They must be consistent:

| `type` | `sql_type` | Use when |
|---|---|---|
| `str` | `TEXT` | Text, codes, names, compliance responses, mixed content |
| `int` | `INTEGER` | Whole numbers: quantities, counts, days, years, port numbers |
| `float` | `REAL` | Decimal numbers: percentages, prices, bandwidth values |
| `bool` | `INTEGER` | Only when genuinely true/false/yes/no with no other values |

SQLite has no native boolean type — use `INTEGER` with values 0 and 1 in the database. The `type: "bool"` in JSON signals intent; `sql_type: "INTEGER"` is what goes into the DDL.

### `fields[].is_primary_key`

Set `true` only when ALL of these are true:
- The field is `sr_no` or an equivalent unique identifier column
- Every row in the source has a non-null, non-`"N/A"` value in this field
- No two rows share the same value in this field — scan every row before deciding
- The source uses structured codes like `VBC.001`, `PTZ.032`, or sequential integers with no gaps

**Before setting `is_primary_key: true`, scan ALL rows in your extracted `rows` array.** If any row has `sr_no: null` or `sr_no: "N/A"` or any repeated value, set `is_primary_key: false`. A column with repeated or null values cannot be a primary key — SQLite will reject the insert.

Set `false` when:
- Any row has `sr_no: null` or `sr_no: "N/A"` — even one such row disqualifies the column
- Any two rows share the same `sr_no` value
- The field is `sr_no` but the source has blank cells (BOQ continuation pattern)
- Any other field — only `sr_no`-type columns can ever be primary keys

When `is_primary_key: true`, the conversion script emits `PRIMARY KEY` on that column in `CREATE TABLE`. When all fields are `false`, the conversion script adds an auto-increment `_row_id` as the primary key.

### `fields[].unit`

**Critical rule: `unit` is the single fixed unit for this column across ALL rows. It is NOT an enumeration of values that appear in the data.**

If every row in a column uses the same unit (e.g. every `quantity` row is measured in `Nos.`), set `unit: "Nos."`.

If the unit varies by row (e.g. some BOQ rows use `Sq. Ft.`, others use `Nos.`, others use `R. Ft.`), that means the unit information lives in a separate `unit` column in the data — not in this field's metadata. In that case, set `unit: null` on the numeric column. Do NOT write `"Nos. | Sq. Ft. | R. Ft."` — that is wrong and breaks the conversion script.

**The test:** ask yourself "does every row in this column use the same unit?" If yes, set it. If no, set `null`.

| Situation | Correct `unit` value |
|---|---|
| `quantity` column in a BOQ where `unit` varies per row | `null` — unit lives in the `unit` column |
| `quantity` column in a spec table where all rows are `Nos.` | `"Nos."` |
| `ir_range` column where all rows specify metres | `"m"` |
| `frame_rate` column where all values are fps | `"fps"` |
| `power` column where values mix W and kW | `null` |

Standard single units for government RFPs:

| Domain | Units |
|---|---|
| Quantity | `Nos.`, `Sets`, `Pairs`, `Lots` |
| Time | `days`, `hours`, `months`, `years` |
| Network/Data | `Mbps`, `Gbps`, `TB`, `GB`, `MB` |
| Power | `W`, `kW`, `VA`, `kVA`, `V`, `A` |
| Physical | `m`, `km`, `mm`, `sq.m` |
| Video | `MP`, `fps`, `lux`, `dB`, `x` (zoom) |
| Financial | `₹`, `₹ Lakhs`, `₹ Crores`, `%` |
| Temperature | `°C` |

### `fields[].source_label`
- Verbatim original column header — mandatory for every column-derived field
- `"Sr. No."` not `"serial_number"` — preserve exactly as written
- `"Make & Model / OEM"` not `"make_model"` — preserve punctuation
- `null` only for fields inferred from prose (no column header exists)

### `fields[].nullable`

**Before setting `nullable: false`, scan your extracted `rows` array for that field.** Count how many rows have `null` for this field. If the count is greater than zero, set `nullable: true`. This is a data scan, not a conceptual judgement about whether the field "should" always have a value.

- `false` — only when **zero rows** in your extracted `rows` have `null` for this field
- `true` — whenever any row has `null` for this field, or when blank cells are possible in the source
- When `is_primary_key: true`, `nullable` must be `false`

**The common mistake to avoid:** setting `nullable: false` because a field like `item` or `parameter` feels like it should always be populated, without checking whether the actual extracted rows contain nulls. The EMS table pattern — where section heading rows have `item` populated but subsequent rows have `item: null` — will produce many null values. The data determines `nullable`, not the field's semantic role.

If code execution is available: `nullable = any(row.get(field_name) is None for row in rows)` gives the correct answer deterministically.

---

## Row Extraction Rules

### Always
- Extract **every data row** — never skip, never sample
- Empty cells → `null` (never `""`, `"N/A"`, `"-"`, `"--"`)
- `"N/A"`, `"-"`, `"--"`, `"Not Applicable"` → `null`
- Coerce numeric strings: `"500"` in `quantity: int` → `500`; `"N/A"` in `quantity: int` → `null`

### Non-consecutive sr_no codes — DO NOT SKIP ROWS

Government RFP spec tables often use alphanumeric `sr_no` codes like `VBC.001`, `PTZ.007`, `ANP.013`. Gaps in the sequence (`PTZ.004` jumping to `PTZ.007`) are **intentional** — intermediate rows exist in the source but were omitted from the pasted excerpt. They are not missing from the source document.

**Rule: extract exactly the rows visible in the input. Do not invent missing rows. Do not skip visible rows.**

If you see `PTZ.004` then `PTZ.007` in the input, your output has exactly those two rows — not four. The gap is the author's choice. Preserve it faithfully.

After extracting, count your rows against the visible rows in the source. If the counts differ, you skipped something. Fix it.

### Mixed sr_no prefixes = multiple sub-tables — SPLIT THEM

If a single markdown table contains rows with different `sr_no` prefixes, those rows represent different equipment types that were merged into one table in the document. They must be split into separate ExtractionResult objects.

**Detection rule:** scan `sr_no` values before extracting. If more than one prefix family appears (e.g. `PAS.*` and `ECB.*`, or `SRV.*` and `NW.*`), that table contains multiple sub-tables.

**Split rule:** one ExtractionResult per prefix family. Each gets its own `table_name`. The `section_path` and `parent_component` are the same for all splits — only `table_name` and `rows` differ.

Example — source table with mixed prefixes:
```
| PAS.001 | PAS system     | Capability to control individual... |
| PAS.013 | Amplifier      | Class D Amplifier with 250W output  |
| ECB.001 | Functional Feat| IP emergency call box with camera   |
| ECB.007 | Inbuilt Camera | 1/2.5" CMOS, 1280x960              |
```

Correct output — two separate ExtractionResult objects:
- `table_name: "component2_pas_spec"` with rows `PAS.001`, `PAS.013`
- `table_name: "component2_ecb_spec"` with rows `ECB.001`, `ECB.007`

Wrong output — one merged ExtractionResult with all 4 rows.

**Note this in the DocumentMap Phase 1:** when you detect a mixed-prefix table during exploration, list it as two separate entries in `Extractable Sections` with a note `"mixed prefix — will split into N sub-tables"`.

### Continuation rows (BOQ pattern)
Rows with empty `sr_no` that extend the previous item's description must be merged:

Source:
```
| 1 | Supply of Fixed Box Cameras    | Nos. | 500 |
|   | including mounting hardware    |      |     |
|   | and installation               |      |     |
```

Extracted:
```json
{"sr_no": 1, "description": "Supply of Fixed Box Cameras including mounting hardware and installation", "unit": "Nos.", "quantity": 500}
```

### Multi-line cells
LlamaParse joins multi-line cells with `<br />`. Preserve as a single string with ` | ` separator:
`"2MP minimum | H.265/H.264 | Day/Night"`

### Multi-tier headers
Grouped header rows produce combined field names:
```
Header: | | Resolution    |         | Frame Rate |
Sub:    | | Horizontal    | Vertical | Min | Max  |
```
Fields: `resolution_horizontal`, `resolution_vertical`, `frame_rate_min`, `frame_rate_max`

### Compliance and deviation columns
These columns are blank in the source (to be filled by bidders). Extract as `null` — **never omit these columns**. They are part of the schema.

---

## What to Extract vs Skip

**Extract:**
- Any markdown table
- Spec compliance tables
- BOQ / Bill of Quantities
- Equipment lists with quantities or specs
- SLA response time tables
- Milestone / payment schedules
- Eligibility / qualification criteria tables
- Approved makes / vendor lists
- Reference standards tables
- Bullet lists where each bullet has a measurable parameter + value

**Skip (`should_extract: false`):**
- Table of contents
- Narrative scope and introductory prose
- Legal disclaimers and standard clauses
- Page headers and footers
- Section titles with no content
- Pure boilerplate ("The bidder shall submit...")

**Edge cases:**
- Section with prose introduction + table → extract table, skip prose, one ExtractionResult
- Section with only headings and no content → skip
- Specs in bullet point paragraphs (no table) → extract as `prose_with_params` using `parameter` and `value` fields
- Repeated identical table in a different section → always a separate ExtractionResult with its own `section_path`

---

## Self-Check Before Each JSON Output

1. Does `section_path` match the actual heading ancestry, not just the table title?
2. Does the `### Extracting:` header above this block contain the **exact same string** as `section_path` in the JSON? If not, fix the header.
3. Does `parent_component` correctly name the top-level component?
4. Is `table_name` prefixed with component/section context and unique in this document?
5. Does `fields` count match the actual column count in the source?
6. Is `source_label` filled for every column-derived field?
7. Is `sql_type` set for every field and consistent with `type`?
8. Is `is_primary_key` set correctly — `true` only for a unique, non-null sr_no-style identifier? (scan all rows before deciding)
9. **`nullable` scan:** for every field where you set `nullable: false` — count the null values for that field across all rows in your `rows` array. If count > 0, change to `nullable: true`. Do not rely on conceptual judgement about what "should" be populated. Use code execution if available: `any(row.get(field_name) is None for row in rows)`.
10. Are `nullable` and `is_primary_key` consistent — a primary key field must have `nullable: false`?
10. **`unit` check:** for each field with a non-null `unit` — does every single row in the source use that same unit? If units vary by row, set `unit: null`. Never write pipe-separated enumerations like `"Nos. | Sq. Ft."` in a `unit` field.
11. **Row count check:** count visible data rows in source → set `source_row_count`. Count your extracted rows → set `row_count`. If `row_count` > `source_row_count`, you invented rows. If `row_count` < `source_row_count` and no continuation rows were merged, you skipped rows. Fix before outputting.
12. **Prefix check:** scan all `sr_no` values. Do they share one prefix family? If not, split into separate ExtractionResult objects.
13. Are empty cells `null`, not empty strings?
14. Are numeric strings coerced to match `fields[].type`?
15. Are continuation rows merged into a single row?
16. **`req_type` / `req_value` check (spec compliance tables only):** does every row have `req_type` set to exactly one of the five valid values? For every row where `req_type = "atomic"`, is `req_value` populated with the extracted value (not the full cell text)? For every other `req_type`, is `req_value: null`?

Fix before outputting. Do not output a JSON block that fails any of these.

**Additional check for the SchemaManifest (runs after all ExtractionResult blocks are done):**

Before writing the manifest, count how many `ExtractionResult` blocks in this session had `should_extract: true`. That count is `total_tables`. The `tables` array in the manifest must have exactly that many entries — one per extracted table. Count them. If `len(tables) != total_tables`, you are missing entries. Find them and add them.

---

## Closing SchemaManifest

After the final `## Extraction Complete` line, always output one additional JSON block — the `SchemaManifest`. This is what the SQLite conversion script uses as its source of truth for creating all tables before inserting any rows.

**CRITICAL: The `tables` array must contain one entry for every table where `should_extract: true` in this session — no exceptions.** Before writing the manifest, count the number of `ExtractionResult` blocks in this session where `should_extract: true`. That number must equal `len(tables)` in the manifest. If you produced 11 extraction blocks, the manifest has 11 entries. If you produced 3, it has 3. A manifest with fewer entries than extractions will cause the conversion script to silently skip table creation for the missing tables, and those tables' rows will fail to insert.

**How to build the manifest without missing tables:** as you produce each `ExtractionResult` block, mentally append its entry to a running list. When you reach `## Extraction Complete`, write that list out as the `tables` array. Do not reconstruct from memory at the end — build it incrementally.

```json
{
  "type": "SchemaManifest",
  "document_name": "filename or null",
  "extraction_timestamp": "ISO timestamp of this extraction",
  "total_tables": 3,
  "tables": [
    {
      "table_name": "component2_fixed_box_camera_spec",
      "physical_table_name": "component2_fixed_box_camera_spec",
      "schema_version": 1,
      "content_type": "spec_compliance_table",
      "section_path": "Component 2 > 2.3 Technical Specifications > 2.3.1 Fixed Box Camera",
      "parent_component": "Component 2: CCTV Based Surveillance System",
      "row_count": 5,
      "ddl_columns": [
        {"name": "sr_no", "sql_type": "TEXT", "nullable": false, "is_primary_key": true},
        {"name": "parameter", "sql_type": "TEXT", "nullable": false, "is_primary_key": false},
        {"name": "minimum_requirement", "sql_type": "TEXT", "nullable": false, "is_primary_key": false},
        {"name": "compliance", "sql_type": "TEXT", "nullable": true, "is_primary_key": false},
        {"name": "deviations", "sql_type": "TEXT", "nullable": true, "is_primary_key": false}
      ],
      "lineage_columns": [
        {"name": "_section_path", "sql_type": "TEXT"},
        {"name": "_parent_component", "sql_type": "TEXT"},
        {"name": "_source_row_count", "sql_type": "INTEGER"},
        {"name": "_extracted_at", "sql_type": "TEXT"}
      ]
    }
  ]
}
```

**`total_tables`** — a new top-level field. Set it to the count of `ExtractionResult` blocks where `should_extract: true` in this session. The conversion script compares `total_tables` against `len(tables)` and raises an error if they differ. This is the manifest's self-validation mechanism.

**`ddl_columns`** — only the LLM-invented columns from `fields`. Copy from the corresponding `ExtractionResult.fields` — do not reinvent them. The column names, sql_types, nullable, and is_primary_key values must be identical to what was in the ExtractionResult.

**`lineage_columns`** — fixed, always exactly these four, never varied:
- `_section_path TEXT`
- `_parent_component TEXT`
- `_source_row_count INTEGER`
- `_extracted_at TEXT`

**`req_type` and `req_value`** — these are data columns, not lineage columns. They are part of the LLM-invented row data for spec compliance tables and therefore appear in `ddl_columns`, not `lineage_columns`. When building the manifest for a spec compliance table, always include them:

```json
{"name": "req_type", "sql_type": "TEXT", "nullable": false, "is_primary_key": false},
{"name": "req_value", "sql_type": "TEXT", "nullable": true, "is_primary_key": false}
```

For non-spec-compliance tables (BOQ, equipment lists, etc.), do not include these columns.

The `type: "SchemaManifest"` field is what the conversion script uses to distinguish this block from `ExtractionResult` blocks when parsing the markdown file.

---

## Complete Example

### Input
```
# Noida Safe City — Volume 2: Technical Specifications

## Component 2: CCTV Based Surveillance System

### 2.1 Scope
The scope of work under this component includes supply, installation,
testing and commissioning of IP-based CCTV cameras...

### 2.3 Technical Specifications

#### 2.3.1 Fixed Box Camera

| Sr. No. | Parameter | Minimum Requirement Description | Compliance (Yes/No/Partial) | Deviations if any |
|---|---|---|---|---|
| 1 | Image Sensor | 1/2.8" Progressive Scan CMOS | | |
| 2 | Resolution | 2MP (1920x1080) | | |
| 3 | Frame Rate | 25 fps at full resolution | | |
| 4 | IR Range | 30 metres minimum | | |
| 5 | IP Rating | IP66 minimum | | |

#### 2.3.2 PTZ Camera

| Sr. No. | Parameter | Minimum Requirement Description | Compliance (Yes/No/Partial) | Deviations if any |
|---|---|---|---|---|
| 1 | Resolution | 2MP minimum | | |
| 2 | Optical Zoom | 30x minimum | | |
| 3 | Pan Range | 360° continuous | | |

### 2.5 Bill of Quantities

| Sr. No. | Description | Unit | Quantity |
|---|---|---|---|
| 1 | Fixed Box Camera (2MP, IR, IP66) | Nos. | 500 |
|   | including supply, installation,  |      |     |
|   | testing and commissioning        |      |     |
| 2 | PTZ Camera (2MP, 30x zoom)       | Nos. | 50  |
| 3 | Camera Mounting Pole (3m, GI)    | Nos. | 420 |
```

---

### Phase 1 Output

## Document Map

**Document:** Pasted content
**Detected structure:** Single-component excerpt (Component 2: CCTV) with 2 spec compliance tables and 1 BOQ table. Standard Indian safe city RFP pattern.

### Hierarchy
- Component 2: CCTV Based Surveillance System
  - 2.1 Scope *(prose only — skip)*
  - 2.3 Technical Specifications
    - 2.3.1 Fixed Box Camera *(spec_compliance_table, 5 rows)*
    - 2.3.2 PTZ Camera *(spec_compliance_table, 3 rows)*
  - 2.5 Bill of Quantities *(boq_table, 3 items with continuation rows)*

### Extractable Sections
- `Component 2 > 2.3 Technical Specifications > 2.3.1 Fixed Box Camera` | spec_compliance_table | 5 rows
- `Component 2 > 2.3 Technical Specifications > 2.3.2 PTZ Camera` | spec_compliance_table | 3 rows
- `Component 2 > 2.5 Bill of Quantities` | boq_table | 3 items

### Sections to Skip
- `Component 2 > 2.1 Scope` | narrative prose, no tables

### Cross-cutting Patterns
- Same 5-column compliance schema across both camera spec sections
- BOQ row 1 has 2 continuation rows — will be merged

```json
{
  "document_name": null,
  "total_sections_found": 4,
  "extractable_count": 3,
  "skip_count": 1,
  "components": [
    {
      "component_id": "Component 2",
      "component_name": "CCTV Based Surveillance System",
      "sections": [
        {
          "section_path": "Component 2 > 2.3 Technical Specifications > 2.3.1 Fixed Box Camera",
          "heading_depth": 3,
          "content_type": "spec_compliance_table",
          "table_count": 1,
          "estimated_rows": 5,
          "extraction_priority": "high",
          "notes": "Compliance and deviation columns blank — extract as null, do not omit"
        },
        {
          "section_path": "Component 2 > 2.3 Technical Specifications > 2.3.2 PTZ Camera",
          "heading_depth": 3,
          "content_type": "spec_compliance_table",
          "table_count": 1,
          "estimated_rows": 3,
          "extraction_priority": "high",
          "notes": "Same column pattern as Fixed Box Camera — always a separate table"
        },
        {
          "section_path": "Component 2 > 2.5 Bill of Quantities",
          "heading_depth": 2,
          "content_type": "boq_table",
          "table_count": 1,
          "estimated_rows": 3,
          "extraction_priority": "high",
          "notes": "Row 1 has 2 continuation rows — will merge into single description"
        }
      ]
    }
  ],
  "cross_cutting_patterns": [
    "Same 5-column compliance pattern across both camera spec sections",
    "BOQ continuation row pattern present"
  ]
}
```

---

### Phase 2 Output

### Extracting: Component 2 > 2.3 Technical Specifications > 2.3.1 Fixed Box Camera

```json
{
  "section_path": "Component 2 > 2.3 Technical Specifications > 2.3.1 Fixed Box Camera",
  "heading_depth": 3,
  "parent_component": "Component 2: CCTV Based Surveillance System",
  "content_type": "spec_compliance_table",
  "should_extract": true,
  "skip_reason": null,
  "table_name": "component2_fixed_box_camera_spec",
  "physical_table_name": "component2_fixed_box_camera_spec",
  "schema_version": 1,
  "rationale": "Technical specification compliance table for fixed box cameras with 5 parameters and minimum requirements",
  "fields": [
    {"name": "sr_no", "type": "int", "sql_type": "INTEGER", "description": "Serial number", "nullable": false, "is_primary_key": true, "unit": null, "source_label": "Sr. No."},
    {"name": "parameter", "type": "str", "sql_type": "TEXT", "description": "Technical parameter name", "nullable": false, "is_primary_key": false, "unit": null, "source_label": "Parameter"},
    {"name": "minimum_requirement", "type": "str", "sql_type": "TEXT", "description": "Minimum specification required by the RFP", "nullable": false, "is_primary_key": false, "unit": null, "source_label": "Minimum Requirement Description"},
    {"name": "compliance", "type": "str", "sql_type": "TEXT", "description": "Bidder's compliance response — Yes, No, or Partial", "nullable": true, "is_primary_key": false, "unit": null, "source_label": "Compliance (Yes/No/Partial)"},
    {"name": "deviations", "type": "str", "sql_type": "TEXT", "description": "Any deviations from the minimum requirement stated by the bidder", "nullable": true, "is_primary_key": false, "unit": null, "source_label": "Deviations if any"}
  ],
  "row_count": 5,
  "source_row_count": 5,
  "rows": [
    {"sr_no": 1, "parameter": "Image Sensor", "minimum_requirement": "1/2.8\" Progressive Scan CMOS", "compliance": null, "deviations": null, "req_type": "atomic", "req_value": "1/2.8\" Progressive Scan CMOS"},
    {"sr_no": 2, "parameter": "Resolution", "minimum_requirement": "2MP (1920x1080)", "compliance": null, "deviations": null, "req_type": "atomic", "req_value": "2MP"},
    {"sr_no": 3, "parameter": "Frame Rate", "minimum_requirement": "25 fps at full resolution", "compliance": null, "deviations": null, "req_type": "atomic", "req_value": "25"},
    {"sr_no": 4, "parameter": "IR Range", "minimum_requirement": "30 metres minimum", "compliance": null, "deviations": null, "req_type": "atomic", "req_value": "30"},
    {"sr_no": 5, "parameter": "IP Rating", "minimum_requirement": "IP66 minimum", "compliance": null, "deviations": null, "req_type": "atomic", "req_value": "IP66"}
  ]
}
```

### Extracting: Component 2 > 2.3 Technical Specifications > 2.3.2 PTZ Camera

```json
{
  "section_path": "Component 2 > 2.3 Technical Specifications > 2.3.2 PTZ Camera",
  "heading_depth": 3,
  "parent_component": "Component 2: CCTV Based Surveillance System",
  "content_type": "spec_compliance_table",
  "should_extract": true,
  "skip_reason": null,
  "table_name": "component2_ptz_camera_spec",
  "physical_table_name": "component2_ptz_camera_spec",
  "schema_version": 1,
  "rationale": "Technical specification compliance table for PTZ cameras — separate table from fixed box camera despite identical column structure",
  "fields": [
    {"name": "sr_no", "type": "int", "sql_type": "INTEGER", "description": "Serial number", "nullable": false, "is_primary_key": true, "unit": null, "source_label": "Sr. No."},
    {"name": "parameter", "type": "str", "sql_type": "TEXT", "description": "Technical parameter name", "nullable": false, "is_primary_key": false, "unit": null, "source_label": "Parameter"},
    {"name": "minimum_requirement", "type": "str", "sql_type": "TEXT", "description": "Minimum specification required by the RFP", "nullable": false, "is_primary_key": false, "unit": null, "source_label": "Minimum Requirement Description"},
    {"name": "compliance", "type": "str", "sql_type": "TEXT", "description": "Bidder compliance response", "nullable": true, "is_primary_key": false, "unit": null, "source_label": "Compliance (Yes/No/Partial)"},
    {"name": "deviations", "type": "str", "sql_type": "TEXT", "description": "Deviations from minimum requirement", "nullable": true, "is_primary_key": false, "unit": null, "source_label": "Deviations if any"}
  ],
  "row_count": 3,
  "source_row_count": 3,
  "rows": [
    {"sr_no": 1, "parameter": "Resolution", "minimum_requirement": "2MP minimum", "compliance": null, "deviations": null, "req_type": "atomic", "req_value": "2MP"},
    {"sr_no": 2, "parameter": "Optical Zoom", "minimum_requirement": "30x minimum", "compliance": null, "deviations": null, "req_type": "atomic", "req_value": "30x"},
    {"sr_no": 3, "parameter": "Pan Range", "minimum_requirement": "360° continuous", "compliance": null, "deviations": null, "req_type": "atomic", "req_value": "360°"}
  ]
}
```

### Extracting: Component 2 > 2.5 Bill of Quantities

```json
{
  "section_path": "Component 2 > 2.5 Bill of Quantities",
  "heading_depth": 2,
  "parent_component": "Component 2: CCTV Based Surveillance System",
  "content_type": "boq_table",
  "should_extract": true,
  "skip_reason": null,
  "table_name": "component2_boq",
  "physical_table_name": "component2_boq",
  "schema_version": 1,
  "rationale": "Bill of Quantities for Component 2 CCTV items — 3 line items, continuation rows merged",
  "fields": [
    {"name": "sr_no", "type": "int", "sql_type": "INTEGER", "description": "Serial number", "nullable": true, "is_primary_key": false, "unit": null, "source_label": "Sr. No."},
    {"name": "description", "type": "str", "sql_type": "TEXT", "description": "Full item description including scope of supply and installation", "nullable": false, "is_primary_key": false, "unit": null, "source_label": "Description"},
    {"name": "unit", "type": "str", "sql_type": "TEXT", "description": "Unit of measurement", "nullable": false, "is_primary_key": false, "unit": null, "source_label": "Unit"},
    {"name": "quantity", "type": "int", "sql_type": "INTEGER", "description": "Number of units to be supplied and installed", "nullable": false, "is_primary_key": false, "unit": "Nos.", "source_label": "Quantity"}
  ],
  "row_count": 3,
  "source_row_count": 5,
  "rows": [
    {"sr_no": 1, "description": "Fixed Box Camera (2MP, IR, IP66) including supply, installation, testing and commissioning", "unit": "Nos.", "quantity": 500},
    {"sr_no": 2, "description": "PTZ Camera (2MP, 30x zoom)", "unit": "Nos.", "quantity": 50},
    {"sr_no": 3, "description": "Camera Mounting Pole (3m, GI)", "unit": "Nos.", "quantity": 420}
  ]
}
```

*(Note: BOQ tables do not include `req_type` or `req_value` — those columns are for spec compliance tables only.)*

## Extraction Complete
Extracted: 3 tables | Skipped: 1 section | Total rows: 11

```json
{
  "type": "SchemaManifest",
  "document_name": null,
  "extraction_timestamp": "2026-05-12T00:00:00",
  "total_tables": 3,
  "tables": [
    {
      "table_name": "component2_fixed_box_camera_spec",
      "physical_table_name": "component2_fixed_box_camera_spec",
      "schema_version": 1,
      "content_type": "spec_compliance_table",
      "section_path": "Component 2 > 2.3 Technical Specifications > 2.3.1 Fixed Box Camera",
      "parent_component": "Component 2: CCTV Based Surveillance System",
      "row_count": 5,
      "ddl_columns": [
        {"name": "sr_no", "sql_type": "INTEGER", "nullable": false, "is_primary_key": true},
        {"name": "parameter", "sql_type": "TEXT", "nullable": false, "is_primary_key": false},
        {"name": "minimum_requirement", "sql_type": "TEXT", "nullable": false, "is_primary_key": false},
        {"name": "compliance", "sql_type": "TEXT", "nullable": true, "is_primary_key": false},
        {"name": "deviations", "sql_type": "TEXT", "nullable": true, "is_primary_key": false},
        {"name": "req_type", "sql_type": "TEXT", "nullable": false, "is_primary_key": false},
        {"name": "req_value", "sql_type": "TEXT", "nullable": true, "is_primary_key": false}
      ],
      "lineage_columns": [
        {"name": "_section_path", "sql_type": "TEXT"},
        {"name": "_parent_component", "sql_type": "TEXT"},
        {"name": "_source_row_count", "sql_type": "INTEGER"},
        {"name": "_extracted_at", "sql_type": "TEXT"}
      ]
    },
    {
      "table_name": "component2_ptz_camera_spec",
      "physical_table_name": "component2_ptz_camera_spec",
      "schema_version": 1,
      "content_type": "spec_compliance_table",
      "section_path": "Component 2 > 2.3 Technical Specifications > 2.3.2 PTZ Camera",
      "parent_component": "Component 2: CCTV Based Surveillance System",
      "row_count": 3,
      "ddl_columns": [
        {"name": "sr_no", "sql_type": "INTEGER", "nullable": false, "is_primary_key": true},
        {"name": "parameter", "sql_type": "TEXT", "nullable": false, "is_primary_key": false},
        {"name": "minimum_requirement", "sql_type": "TEXT", "nullable": false, "is_primary_key": false},
        {"name": "compliance", "sql_type": "TEXT", "nullable": true, "is_primary_key": false},
        {"name": "deviations", "sql_type": "TEXT", "nullable": true, "is_primary_key": false},
        {"name": "req_type", "sql_type": "TEXT", "nullable": false, "is_primary_key": false},
        {"name": "req_value", "sql_type": "TEXT", "nullable": true, "is_primary_key": false}
      ],
      "lineage_columns": [
        {"name": "_section_path", "sql_type": "TEXT"},
        {"name": "_parent_component", "sql_type": "TEXT"},
        {"name": "_source_row_count", "sql_type": "INTEGER"},
        {"name": "_extracted_at", "sql_type": "TEXT"}
      ]
    },
    {
      "table_name": "component2_boq",
      "physical_table_name": "component2_boq",
      "schema_version": 1,
      "content_type": "boq_table",
      "section_path": "Component 2 > 2.5 Bill of Quantities",
      "parent_component": "Component 2: CCTV Based Surveillance System",
      "row_count": 3,
      "ddl_columns": [
        {"name": "sr_no", "sql_type": "INTEGER", "nullable": true, "is_primary_key": false},
        {"name": "description", "sql_type": "TEXT", "nullable": false, "is_primary_key": false},
        {"name": "unit", "sql_type": "TEXT", "nullable": false, "is_primary_key": false},
        {"name": "quantity", "sql_type": "INTEGER", "nullable": false, "is_primary_key": false}
      ],
      "lineage_columns": [
        {"name": "_section_path", "sql_type": "TEXT"},
        {"name": "_parent_component", "sql_type": "TEXT"},
        {"name": "_source_row_count", "sql_type": "INTEGER"},
        {"name": "_extracted_at", "sql_type": "TEXT"}
      ]
    }
  ]
}
```

---

## Notes for the Implementing LLM

- Phase 1 is not optional. Even a single pasted table must produce a mini DocumentMap before extraction.
- Two tables with identical columns but different `section_path` values are always separate ExtractionResult objects. The `section_path` carries the meaning, not just the columns.
- `table_name` must always be prefixed with component/section context. `camera_spec` is wrong. `component2_fixed_box_camera_spec` is correct.
- `source_label` is mandatory for every column-derived field. It is the audit trail connecting the database back to the original document.
- The `ExtractionResult` JSON schema is fixed. Do not add or remove top-level keys.
- When in doubt, extract. A false positive is cheaper than a missed table.
- For large documents (>20 extractable sections): ask for confirmation before extracting all. Extract by component.

**If code execution is available, use it for these specific tasks only:**

Use code execution for:
- Counting extracted rows to set `row_count` and verify against `source_row_count`
- Verifying `sr_no` uniqueness before setting `is_primary_key: true` — run `len(set(sr_nos)) == len(sr_nos) and 'N/A' not in sr_nos and None not in sr_nos`
- Building the `SchemaManifest.tables` array by accumulating entries as each ExtractionResult is produced
- Verifying `total_tables == len(tables)` before outputting the manifest

Do NOT use code execution for:
- Reading or parsing markdown tables — that is a text reading task, not a computation
- Deciding what to extract or skip — that is a semantic judgement task
- Building field definitions or writing row values — those come from reading the source
- Any task where the answer comes directly from reading, not calculating
