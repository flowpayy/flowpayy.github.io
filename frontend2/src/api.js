import axios from 'axios';

const api = axios.create({
  baseURL: 'http://localhost:8000/v1',
});

export const FlowPayAPI = {
  // Collects
  getCollectsByPayer: async (payerId) => {
    const res = await api.get(`/collects?payer_id=${payerId}`);
    return res.data;
  },
  createCollect: async (data) => {
    const res = await api.post('/collects', data);
    return res.data;
  },
  approveCollect: async (id) => {
    const res = await api.post(`/collects/${id}/approve`);
    return res.data;
  },
  declineCollect: async (id) => {
    const res = await api.post(`/collects/${id}/decline`);
    return res.data;
  },

  // Pools
  getPool: async (id) => {
    const res = await api.get(`/pools/${id}`);
    return res.data;
  },
  createPool: async (data) => {
    const res = await api.post('/pools', data);
    return res.data;
  },
  contributeToPool: async (id, data) => {
    const res = await api.post(`/pools/${id}/contribute`, data);
    return res.data;
  }
};
