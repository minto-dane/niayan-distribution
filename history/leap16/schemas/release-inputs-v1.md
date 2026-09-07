# Release inputs v1

The executable strict schema is `tools/distroctl.py`: unknown fields fail.
Envelope: format(1), payload, exactly two signatures (build/security).
Canonical JSON uses sorted keys, compact separators, ASCII escapes; floats/nonfinite and duplicates are forbidden.
Each role signs `role || NUL || "MissionCore/suse-release-inputs/v1" || NUL || canonical(payload)`.
Authority identity, role, separate domain, validity and public key are externally provisioned.
Source-set and contract expectations come from the independent build plan, not the received envelope.

Payload fields: format/profile/family/architecture/generation/not_before/expires/source_set/contract_profile/
profile_sha256/repositories/packages/input_files/obligations. See tests for artificial fixtures, not a real repository.
Each repository carries source URL, local snapshot path, repomd hash, key path/hash, exact family/release.
Each package carries full NEVRA, owning repository, relative RPM path, SHA256 and bootstrap/image stage.
Every file under the cache must be listed. No special files, symlinks, external paths or plaintext credential URLs.
Acceptance lifetime is bounded to seven days; floor persists outside the rollback target.

Current limitations: metadata checks do not verify upstream signatures or solve dependencies.
Obligation labels cannot create qualification. Test mode is API-only in test fixtures and rejected by the CLI.
