/** @type import('hardhat/config').HardhatUserConfig */
require("@nomicfoundation/hardhat-toolbox");

module.exports = {
  solidity: "0.8.0",
  defaultNetwork: "localhost",
  networks: {
    localhost: {
      url: "http://127.0.0.1:8545",
    },
    besu: {
      url: process.env.BESU_RPC_URL || "http://localhost:8545",
      accounts:
        process.env.ANCHOR_PRIVATE_KEY && process.env.ANCHOR_PRIVATE_KEY.length > 0
          ? [process.env.ANCHOR_PRIVATE_KEY]
          : [],
    },
  },
  paths: {
    sources: "./contracts",
    tests: "./test",
    cache: "./cache",
    artifacts: "./artifacts",
  },
};
