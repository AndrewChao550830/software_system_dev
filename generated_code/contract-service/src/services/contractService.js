const Contract = require('../models/Contract');
const User = require('../models/User');
const { Op } = require('sequelize');
const workflowService = require('./workflowService');
const notificationService = require('./notificationService');
const auditLogService = require('./auditLogService');

async function createContract(contractData) {
  // Check for duplicate contract number
  const existing = await Contract.findOne({ where: { contract_number: contractData.contract_number } });
  if (existing) throw new Error('Contract number already exists');

  // Validate submitted_by user exists and is active
  const user = await User.findByPk(contractData.submitted_by);
  if (!user || !user.is_active) throw new Error('Invalid or inactive user');

  const contract = await Contract.create({
    ...contractData,
    status: 'Draft'
  });

  await auditLogService.logEvent('Contract', contract.contract_id, 'CREATE', req.user.user_id, {
    previous: null,
    current: contract.get()
  });

  return contract;
}

async function listContracts(filters) {
  const where = {};
  if (filters.status) where.status = filters.status;
  if (filters.submitted_by) where.submitted_by = filters.submitted_by;
  return Contract.findAll({ where });
}

async function getContractById(id) {
  return Contract.findByPk(id);
}

async function updateContract(id, updateData) {
  const contract = await Contract.findByPk(id);
  if (!contract) throw new Error('Contract not found');

  // Prevent updating submitted_by or other immutable fields
  delete updateData.submitted_by;
  delete updateData.contract_number;

  await contract.update(updateData);
  return contract;
}

async function submitContract(id, userId) {
  const contract = await Contract.findByPk(id);
  if (!contract) throw new Error('Contract not found');
  if (contract.status !== 'Draft') throw new Error('Only draft contracts can be submitted');
  if (contract.submitted_by.toString() !== userId.toString()) throw new Error('Unauthorized');

  await contract.update({ status: 'Submitted', submitted_date: new Date() });
  await workflowService.routeForApproval(id);

  await auditLogService.logEvent('Contract', contract.contract_id, 'SUBMIT', userId, {
    previous: { status: 'Draft' },
    current: { status: 'Submitted' }
  });

  await notificationService.sendNotification(contract.contract_id, 'ContractSubmitted');

  return contract;
}

async function approveContract(id, approverId) {
  const contract = await Contract.findByPk(id);
  if (!contract) throw new Error('Contract not found');
  if (contract.status !== 'UnderReview') throw new Error('Contract is not under review');

  await contract.update({ status: 'Approved', approved_by: approverId, approved_date: new Date() });

  await auditLogService.logEvent('Contract', contract.contract_id, 'APPROVE', approverId, {
    previous: { status: 'UnderReview' },
    current: { status: 'Approved' }
  });

  await notificationService.sendNotification(contract.contract_id, 'ContractApproved');
  // Trigger AI scoring (via Kafka or direct call)
  // In a real system, this would publish a message to a scoring request topic

  return contract;
}

async function rejectContract(id, rejectorId, comments) {
  const contract = await Contract.findByPk(id);
  if (!contract) throw new Error('Contract not found');
  if (['Draft', 'Submitted', 'UnderReview'].includes(contract.status) === false) {
    throw new Error('Contract cannot be rejected in current status');
  }

  await contract.update({ status: 'Rejected', approved_by: rejectorId, approved_date: new Date() });

  await auditLogService.logEvent('Contract', contract.contract_id, 'REJECT', rejectorId, {
    previous: { status: contract.status },
    current: { status: 'Rejected' }
  });

  await notificationService.sendNotification(contract.contract_id, 'ContractRejected', { comments });

  return contract;
}

async function archiveContract(id) {
  const contract = await Contract.findByPk(id);
  if (!contract) throw new Error('Contract not found');
  if (!['Approved', 'Rejected'].includes(contract.status)) {
    throw new Error('Only approved or rejected contracts can be archived');
  }

  await contract.update({ status: 'Archived' });

  await auditLogService.logEvent('Contract', contract.contract_id, 'ARCHIVE', req.user.user_id, {
    previous: { status: contract.status },
    current: { status: 'Archived' }
  });

  return contract;
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