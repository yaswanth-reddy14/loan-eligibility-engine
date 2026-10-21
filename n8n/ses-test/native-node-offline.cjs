// Execute the installed node with synthetic inputs and a mocked HTTP helper only.
const assert = require('node:assert/strict');
let blockedNetworkAttempts = 0;
const block = () => { blockedNetworkAttempts++; throw new Error('Network is forbidden in this offline test'); };
require('node:http').request = block;
require('node:https').request = block;
require('node:net').connect = block;
require('node:net').createConnection = block;
global.fetch = block;
const base = '/usr/local/lib/node_modules/n8n/node_modules/n8n-nodes-base/dist/';
const { AwsSes } = require(base + 'nodes/Aws/SES/AwsSes.node.js');
const { Aws } = require(base + 'credentials/Aws.credentials.js');

async function main() {
  const node = new AwsSes();
  const credential = new Aws();
  assert.equal(node.description.version, 1);
  for (const key of ['region', 'accessKeyId', 'secretAccessKey', 'temporaryCredentials', 'sessionToken']) {
    assert(credential.properties.some(p => p.name === key));
  }
  const results = [];
  for (const outcome of ['success', 'rejection', 'timeout']) {
    let calls = 0;
    const params = {
      authentication: 'iam', resource: 'email', operation: 'send',
      fromEmail: 'sender@example.invalid', toAddresses: ['recipient@example.invalid'],
      subject: '[OFFLINE] Synthetic eligibility', body: '<p>Synthetic only</p>',
      isBodyHtml: true, additionalFields: {},
    };
    const context = {
      getInputData: () => [{ json: {} }],
      getNodeParameter: name => params[name],
      getCredentials: async type => { assert.equal(type, 'aws'); return { region: 'ap-south-1' }; },
      getNode: () => ({ name: 'Offline SES', type: 'n8n-nodes-base.awsSes', typeVersion: 1, parameters: params }),
      continueOnFail: () => true,
      logger: { warn: () => {} },
      helpers: {
        requestWithAuthentication: async (type, request) => {
          calls++;
          assert.equal(type, 'aws');
          assert.equal(request.region, 'ap-south-1');
          assert.equal(request.method, 'POST');
          const query = new URLSearchParams(request.qs.path.split('?')[1]);
          assert.equal(query.get('Action'), 'SendEmail');
          assert.equal(query.get('Source'), params.fromEmail);
          assert.equal(query.get('Destination.ToAddresses.member.1'), params.toAddresses[0]);
          assert(!query.has('Destination.ToAddresses.member.2'));
          assert(![...query.keys()].some(k => /CcAddresses|BccAddresses/.test(k)));
          if (outcome !== 'success') throw new Error(outcome === 'timeout' ? 'Read timeout' : 'MessageRejected');
          return '<SendEmailResponse><SendEmailResult><MessageId>offline-message-id</MessageId></SendEmailResult></SendEmailResponse>';
        },
        returnJsonArray: value => [{ json: value }],
        constructExecutionMetaData: value => value,
      },
    };
    const output = await node.execute.call(context);
    assert.equal(calls, 1, 'Native node must not repeat the mocked request');
    if (outcome === 'success') assert.equal(output[0][0].json.SendEmailResponse.SendEmailResult.MessageId, 'offline-message-id');
    else assert.equal(typeof output[0][0].json.error, 'string');
    results.push({ outcome, mocked_request_calls: calls, status: 'PASS' });
  }
  // Credential signing is local computation with invented values, not credential installation.
  const signed = await credential.authenticate({
    region: 'ap-south-1', accessKeyId: 'OFFLINE_NOT_AN_AWS_KEY', secretAccessKey: 'offline-placeholder',
    temporaryCredentials: true, sessionToken: 'offline-session-token',
  }, { method: 'POST', qs: { service: 'email', path: '/?Action=SendEmail' }, headers: {} });
  assert.equal(new URL(signed.url).hostname, 'email.ap-south-1.amazonaws.com');
  assert(Object.entries(signed.headers).some(([k,v]) => k.toLowerCase() === 'x-amz-security-token' && v === 'offline-session-token'));
  assert.equal(blockedNetworkAttempts, 0);
  console.log(JSON.stringify({ node_version: 1, cases: results, temporary_session_token_signing: 'PASS', network_attempts: blockedNetworkAttempts }));
}
main().catch(error => { console.error(error); process.exitCode = 1; });
