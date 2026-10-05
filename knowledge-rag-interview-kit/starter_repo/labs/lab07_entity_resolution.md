# Lab 7: Entity Resolution, Near-Duplicates and Contradictions

Code: [app/refinement/entity_resolution.py](../app/refinement/entity_resolution.py) · Tests: [tests/test_entity_resolution.py](../tests/test_entity_resolution.py) · API: `/refinement/*` in Swagger (`/docs`).

All three features are **pure functions**. They take records in and return decisions out, with no database and no model. That makes every decision explainable and testable, which is what you want for data that feeds a knowledge graph.

## 1. Why this matters

Different systems name the same thing differently:

| Source | Record |
|---|---|
| CRM | `Acme Inc`, country US |
| Contracts | `ACME Incorporated`, LEI `5493001KJTIIGC8Y1R12` |
| News feed | `Acme` |
| Registry | `Acme Ltd`, country **UK**, different registration |

If you don't resolve these, the graph from Lab 6 has four "Acme" nodes and multi-hop questions miss facts. If you resolve them too eagerly, you merge a US company with an unrelated UK company, and answers mix two companies' facts. **A wrong merge is worse than a missed merge**, which is why uncertain pairs go to a human review queue.

## 2. The pipeline (read the code in this order)

```text
normalize_name -> blocking_keys -> compare (pairwise) -> resolve (union-find + guard) -> canonical entities + review queue
```

1. **`normalize_name`** makes names comparable: `"ACME, Inc."` and `"Acme Incorporated"` both become `acme`. It uses NFKC width folding, lower-casing, punctuation removal, and legal-suffix removal, including Chinese suffixes like `有限公司`.
2. **`blocking_keys`** avoids comparing every pair (n² pairs is 50 billion for 100k records). A record is only compared with records that share a key: the same identifier, the same first 3 name characters, or the same alias group. *Trade-off:* a true match with no shared key is never found.
3. **`compare`** scores one pair. Its rules, in order:
   - A different `type` means distinct.
   - A shared identifier (LEI, registration number) with the **same** value means merge (score 1.0).
   - The same identifier key with **different** values means distinct, whatever the names say.
   - An alias table maintained by domain experts gives 0.95.
   - Otherwise, name similarity: the maximum of character similarity and token Jaccard. Context then adjusts the score: same country +0.03, different country −0.3.
   - A score ≥ 0.92 merges, 0.75–0.92 goes to **review**, and anything lower stays distinct.
4. **`resolve`** clusters merges with union-find, strongest evidence first. It has a **transitivity guard**: if A≈B and B≈C but A and C carry conflicting LEIs, it refuses the merge and sends it to review.
5. The canonical entity takes its name from the **most authoritative source**. The other names become aliases.

### Why not use embeddings for identity?

"Apple Inc" and "Apple Ltd" are semantically close and may still be different legal entities. Embeddings measure *similarity*, not *identity*. Use them at most to *generate candidates*, never to decide merges.

## 3. Near-duplicate documents

`near_duplicates` compares **shingles** (3-word windows, or 3-character windows for Chinese) with Jaccard similarity. Exact Jaccard is O(n²). At scale, **MinHash + LSH** estimates the same number without comparing every pair, and the decision rule stays the same. Near-duplicates waste index space and fill the top-K with the same passage twice.

## 4. Contradiction detection

`find_conflicts` groups claims by (entity, property). When values differ:

1. A **later effective date** wins, because newer supersedes older.
2. If the dates are the same, **higher source authority** wins.
3. If the best disagreeing claims tie on both, the result is **needs_review**, with no automatic winner.

This keeps an old policy from silently overriding a new one, while keeping history for audit.

## 5. Try it

With the API running, open `/docs` and call `POST /refinement/entities/resolve` with:

```json
{
  "records": [
    {"id": "crm-1", "name": "Acme Inc", "type": "Company", "attributes": {"country": "US"}, "authority": 1},
    {"id": "ctr-7", "name": "ACME Incorporated", "type": "Company", "attributes": {"country": "US"}, "authority": 2},
    {"id": "reg-3", "name": "Acme Ltd", "type": "Company", "attributes": {"country": "UK"}},
    {"id": "r1", "name": "International Business Machines", "type": "Company", "authority": 2},
    {"id": "r2", "name": "IBM", "type": "Company"}
  ],
  "aliases": {"ibm": "ibm", "international business machines": "ibm"}
}
```

Expected: `crm-1` + `ctr-7` merge (named "ACME Incorporated", the higher authority), `reg-3` stays separate (different country), and `r1` + `r2` merge via the alias table. Read `decisions[].reasons` to see *why*.

Then try `POST /refinement/contradictions` with two CEO claims that have different effective dates, and two with the same date and authority.

## 6. Exercises

1. Add a `city` difference to the Acme pair and watch the score drop into review.
2. Lower `MERGE_THRESHOLD` to 0.8 and find a test that now wrongly merges. That's the precision/recall trade-off in one line.
3. Write a test where blocking hides a true match (two names with different first 3 letters and no identifiers). How would you add a second blocking key?
4. Connect it: after Lab 6 extraction, run `resolve` over the extracted entities before writing to Neo4j.

## 7. Interview talking points

- "Identifiers first, then names plus context. Anything uncertain goes to review, because a wrong merge corrupts every downstream answer."
- "Blocking makes it scale, but it caps recall. I measure the recall loss on a labelled sample."
- "Merges need a transitivity guard, or conflicting identifiers get merged through a middle record."
- "Contradictions resolve by effective date, then authority, else review. Superseded values stay for audit."
