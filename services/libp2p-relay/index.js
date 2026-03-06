const express = require('express');
const bodyParser = require('body-parser');
const { create } = require('@libp2p/js-libp2p');
const { tcp } = require('@libp2p/tcp');
const { webSockets } = require('@libp2p/websockets');
const { mplex } = require('@libp2p/mplex');
const { bootstrap } = require('@libp2p/bootstrap');

async function createNode() {
  const node = await create({
    transports: [tcp(), webSockets()],
    streamMuxers: [mplex()],
    peerDiscovery: [bootstrap({ list: [] })]
  });
  await node.start();
  return node;
}

async function main() {
  const app = express();
  app.use(bodyParser.json());

  const node = await createNode();
  console.log('libp2p relay node started');

  app.get('/peers', async (req, res) => {
    try {
      const peers = Array.from(node.getConnections().keys());
      res.json({ peers });
    } catch (e) {
      res.status(500).json({ error: e.toString() });
    }
  });

  app.post('/publish', async (req, res) => {
    const topic = req.body.topic;
    const message = req.body.message;
    if (!topic || !message) return res.status(400).json({ error: 'topic and message required' });
    try {
      // use floodsub/pubsub if available; fallback: write to console
      if (node.pubsub && node.pubsub.publish) {
        await node.pubsub.publish(topic, Buffer.from(JSON.stringify(message)));
        return res.json({ ok: true });
      }
      console.log('[publish]', topic, message);
      return res.json({ ok: true, note: 'published-to-log' });
    } catch (e) {
      res.status(500).json({ error: e.toString() });
    }
  });

  const port = process.env.PORT || 15000;
  app.listen(port, () => console.log(`libp2p relay HTTP bridge listening on ${port}`));
}

main().catch(err => {
  console.error('libp2p relay failed', err);
  process.exit(1);
});
