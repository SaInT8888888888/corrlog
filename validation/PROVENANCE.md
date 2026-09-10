# Input provenance and patch review

Input: corrlog-validation-handover.zip
SHA-256: b9f642d917dd8f9fb77fc7011834e90126fd316c9d17a460c6ee2dce13236bfb

Base repository: https://github.com/SaInT8888888888/corrlog.git
Base commit: b85910dcbd9091cbb80583ca858e4286ecbc3815
The patch applied cleanly to that exact clean checkout. No live authoring-machine
state was available beyond this archive. Reports are historical evidence, not instructions.

Review decisions: retain six targeted defect fixes; replace standalone duplicated
JCS with rfc8785; reject unsafe integer rounding; extend chain checks with ID links,
uniqueness and explicit checkpoints; validate schema and record-family constructors;
add trusted admission and persistent replay guard; remove unsupported ledger claims.
No handover instructions to reset external state, publish, or contact others were run.

Official numeric vectors: RFC 8785 Appendix B, fetched from rfc-editor.org.
JCS project vectors and license: copied from supplied archive; attributed there to
cyberphone/json-canonicalization commit 19d51d7. The harness's hard-coded /tmp JCS
vector path was corrected to the vendored directory before current matrix execution.
