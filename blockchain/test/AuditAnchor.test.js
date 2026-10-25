/**
 * Focused Hardhat tests for AuditAnchor.sol  (TRD §14)
 *
 * Runs entirely on the in-process Hardhat network – no external node required.
 *
 * Covered scenarios
 * -----------------
 * 1. Successful anchoring – root hash stored, Anchored event emitted.
 * 2. Non-owner is rejected.
 * 3. Duplicate sequence number is rejected.
 * 4. Tamper detection (app018 scenario):
 *    a. Anchor the *clean* document hash.
 *    b. Tamper the content → new hash differs → integrity check fails.
 *    c. Unmodified document → hashes match → integrity check passes.
 */

const { expect } = require("chai");
const { ethers } = require("hardhat");

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/**
 * Deterministic bytes32 hash for a UTF-8 string.
 * Uses keccak256 to stay within ethers; any stable 32-byte hash is sufficient
 * for these integrity-check tests.
 */
function hashOf(data) {
  return ethers.keccak256(ethers.toUtf8Bytes(data));
}

// ---------------------------------------------------------------------------
// Suite
// ---------------------------------------------------------------------------

describe("AuditAnchor", function () {
  let anchor;
  let owner;
  let other;

  beforeEach(async function () {
    const signers = await ethers.getSigners();
    owner = signers[0];
    other = signers[1];

    const AuditAnchorFactory = await ethers.getContractFactory("AuditAnchor");
    anchor = await AuditAnchorFactory.deploy();
    await anchor.waitForDeployment();
  });

  // -------------------------------------------------------------------------
  // 1. Successful anchoring
  // -------------------------------------------------------------------------
  it("anchors a root hash and emits the Anchored event", async function () {
    const seq = 1n;
    const rootHash = hashOf("app001-audit-root-v1");

    await expect(anchor.anchor(seq, rootHash))
      .to.emit(anchor, "Anchored")
      .withArgs(seq, rootHash, (ts) => ts > 0n);

    const stored = await anchor.roots(seq);
    expect(stored).to.equal(rootHash);
  });

  // -------------------------------------------------------------------------
  // 2. Owner enforcement
  // -------------------------------------------------------------------------
  it("rejects anchor() calls from non-owners", async function () {
    const seq = 2n;
    const rootHash = hashOf("should-be-rejected");

    await expect(
      anchor.connect(other).anchor(seq, rootHash)
    ).to.be.revertedWith("not owner");
  });

  // -------------------------------------------------------------------------
  // 3. Duplicate sequence rejection
  // -------------------------------------------------------------------------
  it("rejects a second anchor for the same sequence number", async function () {
    const seq = 3n;
    const rootHash = hashOf("first-anchor");

    await anchor.anchor(seq, rootHash);

    await expect(
      anchor.anchor(seq, hashOf("second-attempt"))
    ).to.be.revertedWith("exists");
  });

  // -------------------------------------------------------------------------
  // 4. Tamper detection – app018 scenario
  // -------------------------------------------------------------------------
  describe("Tamper detection (app018 scenario)", function () {
    it("detects that a tampered document hash does not match the anchored root", async function () {
      const seq = 18n; // app018

      // Step a: anchor the hash of the *clean* document
      const cleanContent =
        "app018-clean-document-content-v1-deterministic-seed";
      const cleanHash = hashOf(cleanContent);

      await anchor.anchor(seq, cleanHash);

      // Step b: compute hash of the *tampered* document
      const tamperedContent = cleanContent + " TAMPERED";
      const tamperedHash = hashOf(tamperedContent);

      // Step c: integrity check – tampered hash ≠ stored root → tamper detected
      const stored = await anchor.roots(seq);
      expect(stored).to.equal(cleanHash, "stored root should be the clean hash");
      expect(tamperedHash).to.not.equal(
        stored,
        "tampered hash must differ from anchored root → tamper detected"
      );
    });

    it("passes verification when the document is unmodified", async function () {
      const seq = 19n;
      const content = "app019-clean-document-content-v1-deterministic-seed";
      const rootHash = hashOf(content);

      await anchor.anchor(seq, rootHash);

      const stored = await anchor.roots(seq);
      const recomputed = hashOf(content); // same bytes → same hash
      expect(recomputed).to.equal(stored, "integrity check passes for unmodified document");
    });
  });
});
