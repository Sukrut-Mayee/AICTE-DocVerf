// SPDX-License-Identifier: MIT
// AuditAnchor contract per docs/TRD.md section 14.
// Only audit-root hashes are anchored on-chain; never documents or personal data.
pragma solidity ^0.8.0;

contract AuditAnchor {
    event Anchored(uint256 indexed seq, bytes32 rootHash, uint256 timestamp);
    mapping(uint256 => bytes32) public roots;
    address public immutable owner;

    constructor() {
        owner = msg.sender;
    }

    function anchor(uint256 seq, bytes32 rootHash) external {
        require(msg.sender == owner, "not owner");
        require(roots[seq] == bytes32(0), "exists");
        roots[seq] = rootHash;
        emit Anchored(seq, rootHash, block.timestamp);
    }
}
