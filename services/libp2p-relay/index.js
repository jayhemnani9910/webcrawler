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
      // getConnections() returns an array of Connection objects, so .keys()
      // yielded array indices (0, 1, 2) rather than peer identifiers.
      const peers = node.getConnections().map(c => c.remotePeer.toString());
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
      // createNode() configures no pubsub service, so node.pubsub is undefined and
      // nothing here reached a peer. Answering 200 {ok:true} told the caller in
      // src/gossip_distributed.py the message had been published when it had only
      // been written to this process's stdout.
      console.log('[publish-dropped: no pubsub configured]', topic, message);
      return res.status(503).json({
        ok: false,
        error: 'pubsub is not configured on this relay; message was not published'
      });
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
