import { ethers } from "hardhat";

async function main() {
  const [deployer] = await ethers.getSigners();

  console.log("Deploying AuditAnchor with account:", deployer.address);

  const AuditAnchor = await ethers.getContractFactory("AuditAnchor");
  const anchor = await AuditAnchor.deploy();
  await anchor.waitForDeployment();

  const address = await anchor.getAddress();
  console.log("AuditAnchor deployed to:", address);

  // Persist the address for the Python integration layer.
  console.log(
    "Set ANCHOR_CONTRACT_ADDRESS=" + address + " in .env (TRD §14 / §15)"
  );
}

main()
  .then(() => process.exit(0))
  .catch((error) => {
    console.error(error);
    process.exit(1);
  });
