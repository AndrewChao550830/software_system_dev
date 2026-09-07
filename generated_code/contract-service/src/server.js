const express = require('express');
const app = express();
const port = process.env.PORT || 3000;

app.use(express.json());

// Health check endpoint
app.get('/health', (req, res) => res.send('OK'));

// Contract routes
const contractController = require('./controllers/contractController');
app.post('/api/v1/contracts', contractController.createContract);
app.get('/api/v1/contracts', contractController.listContracts);
app.get('/api/v1/contracts/:id', contractController.getContractById);
app.put('/api/v1/contracts/:id', contractController.updateContract);
app.post('/api/v1/contracts/:id/submit', contractController.submitContract);
app.post('/api/v1/contracts/:id/approve', contractController.approveContract);
app.post('/api/v1/contracts/:id/reject', contractController.rejectContract);
app.post('/api/v1/contracts/:id/archive', contractController.archiveContract);

// Auth routes
const authController = require('./controllers/authController');
app.post('/api/v1/auth/login', authController.login);
app.post('/api/v1/auth/refresh', authController.refreshToken);

// Scoring route (placeholder for AI service integration)
app.post('/api/v1/scoring/score', (req, res) => {
  // In reality, this would call the AI scoring service via Kafka or HTTP
  res.status(501).send('Not implemented');
});

// Error handling middleware
app.use(require('./middleware/errorHandler'));

app.listen(port, () => {
  console.log(`Contract service listening on port ${port}`);
});