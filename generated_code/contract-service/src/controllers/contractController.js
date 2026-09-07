const contractService = require('../services/contractService');

async function createContract(req, res) {
  try {
    const contract = await contractService.createContract(req.body);
    res.status(201).json(contract);
  } catch (error) {
    res.status(400).json({ error: error.message });
  }
}

async function listContracts(req, res) {
  try {
    const contracts = await contractService.listContracts(req.query);
    res.json(contracts);
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
}

async function getContractById(req, res) {
  try {
    const contract = await contractService.getContractById(req.params.id);
    if (!contract) return res.status(404).json({ error: 'Contract not found' });
    res.json(contract);
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
}

async function updateContract(req, res) {
  try {
    const contract = await contractService.updateContract(req.params.id, req.body);
    res.json(contract);
  } catch (error) {
    res.status(400).json({ error: error.message });
  }
}

async function submitContract(req, res) {
  try {
    const contract = await contractService.submitContract(req.params.id, req.user.user_id);
    res.json(contract);
  } catch (error) {
    res.status(400).json({ error: error.message });
  }
}

async function approveContract(req, res) {
  try {
    const contract = await contractService.approveContract(req.params.id, req.user.user_id);
    res.json(contract);
  } catch (error) {
    res.status(400).json({ error: error.message });
  }
}

async function rejectContract(req, res) {
  try {
    const contract = await contractService.rejectContract(req.params.id, req.user.user_id, req.body.comments);
    res.json(contract);
  } catch (error) {
    res.status(400).json({ error: error.message });
  }
}

async function archiveContract(req, res) {
  try {
    const contract = await contractService.archiveContract(req.params.id);
    res.json(contract);
  } catch (error) {
    res.status(400).json({ error: error.message });
  }
}

module.exports = {
  createContract,
  listContracts,
  getContractById,
  updateContract,
  submitContract,
  approveContract,
  rejectContract,
  archiveContract
};