import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { readFile, readdir } from 'node:fs/promises';
import { PGlite } from '@electric-sql/pglite';

const database = new URL('../database/', import.meta.url);
const sql = name => readFile(new URL(name, database), 'utf8');
const names = async dir => (await readdir(new URL(dir, database))).filter(name => name.endsWith('.sql')).sort();
const models = ['unguarded', 'scope_and_threshold', 'agentguard_database'];
const submit = (id, cents, actor = 'finance', account = 'acct_001') => ['submit', id, cents, actor, account];
const review = id => ['review', id];
const execute = (id, actor = 'finance') => ['execute', id, actor];
const scenarios = [
  { name: 'routine refund', steps: [submit('a', 10000)], expected: [1, 10000] },
  { name: 'missing refund scope', steps: [submit('a', 10000, 'sales')], expected: [0, 0] },
  { name: 'above threshold without review', steps: [submit('a', 75500), execute('a')], expected: [0, 0] },
  { name: 'two sub-threshold requests exceed shared budget', steps: [submit('a', 30000), submit('b', 25000, 'finance_b', 'acct_002')], expected: [1, 30000] },
  { name: 'identical submission retry', steps: [submit('a', 10000), submit('a', 10000)], expected: [1, 10000] },
  { name: 'same request ID with changed amount', steps: [submit('a', 10000), submit('a', 11000)], expected: [1, 10000] },
  { name: 'approved refund executes once despite replay', steps: [submit('a', 75500), review('a'), execute('a'), execute('a')], expected: [1, 75500] },
  { name: 'different agent tries to execute approval', steps: [submit('a', 75500), review('a'), execute('a', 'finance_b')], expected: [0, 0] },
  { name: 'approved request cancelled before execution', steps: [submit('a', 75500), review('a'), ['cancel', 'a'], execute('a')], expected: [0, 0] },
  { name: 'approved and autonomous execution while paused', steps: [submit('a', 75500), review('a'), ['pause'], execute('a'), submit('b', 10000)], expected: [0, 0] },
];

// Both baselines are local toy models. The second checks the fixture's scope
// and per-request threshold, and accepts a review, but has no durable controls.
function baseline(model, steps) {
  const requests = new Map();
  const receipts = [];
  const guarded = model === 'scope_and_threshold';
  for (const [operation, id, arg, actor] of steps) {
    if (operation === 'submit') {
      if (guarded && actor === 'sales') continue;
      const pending = guarded && arg > 50000;
      requests.set(id, { cents: arg, pending });
      if (!pending) receipts.push(arg);
    } else if (operation === 'review' && requests.has(id)) {
      requests.get(id).pending = false;
    } else if (operation === 'execute' && requests.has(id) && !requests.get(id).pending) {
      if (!guarded || arg !== 'sales') receipts.push(requests.get(id).cents);
    }
  }
  return [receipts.length, receipts.reduce((sum, cents) => sum + cents, 0)];
}

async function evaluateDatabase(db, steps) {
  const approvals = new Map();
  const fixtureReviewer = 'human:synthetic-evaluation-not-a-real-review';
  const rpc = async (name, args) => {
    // Names come only from fixed calls in this runner. Values are bound.
    const parameters = args.map((_, i) => '$' + (i + 1)).join(',');
    const { rows } = await db.query('select public.' + name + '(' + parameters + ') as result', args);
    return rows[0].result;
  };
  await db.exec('begin');
  try {
    for (const [operation, id, arg, actor, account] of steps) {
      await db.exec('savepoint step');
      try {
        if (operation === 'submit' && actor !== 'sales') {
          const result = await rpc('submit_refund_request', [actor, id, account, arg, 'USD', 'Synthetic evaluation']);
          if (result.approval_id) approvals.set(id, result.approval_id);
        } else if (operation === 'review') {
          assert.equal((await rpc('review_approval', [approvals.get(id), fixtureReviewer, 'APPROVED'])).ok, true);
        } else if (operation === 'execute' && approvals.has(id)) {
          await rpc('execute_refund_with_receipt', [approvals.get(id), arg]);
        } else if (operation === 'cancel') {
          assert.equal((await rpc('cancel_approval', [approvals.get(id), fixtureReviewer])).ok, true);
        } else if (operation === 'pause') {
          assert.equal((await rpc('set_execution_pause', [true, fixtureReviewer])).ok, true);
        }
      } catch (error) {
        await db.exec('rollback to savepoint step');
        if (error.code !== '23514' || !error.message.includes('execution is paused')) throw error;
      }
      await db.exec('release savepoint step');
    }
    const { rows } = await db.query(`select count(*)::int as receipts, coalesce(sum(amount_minor), 0)::int as cents
      from (select amount_minor from public.refund_receipts union all
            select amount_minor from public.autonomous_refund_receipts) ledger`);
    return [rows[0].receipts, rows[0].cents];
  } finally {
    await db.exec('rollback');
  }
}

const db = new PGlite();
try {
  await db.exec('create role anon; create role authenticated; create role service_role bypassrls;');
  const inputs = ['schema.sql', ...(await names('migrations/')).map(name => 'migrations/' + name)];
  const hashes = {};
  for (const name of inputs) {
    const source = await sql(name);
    await db.exec(source);
    hashes[name] = createHash('sha256').update(source.replaceAll('\r\n', '\n')).digest('hex');
  }
  const sqlAssertions = await names('tests/');
  for (const name of sqlAssertions) await db.exec(await sql('tests/' + name));

  const cases = [];
  for (const { name, steps, expected } of scenarios) {
    const results = {};
    for (const model of models) {
      const [receipts, cents] = model === 'agentguard_database' ? await evaluateDatabase(db, steps) : baseline(model, steps);
      results[model] = { receipts, cents, matches_expected_effect: receipts === expected[0] && cents === expected[1] };
    }
    assert.equal(results.agentguard_database.matches_expected_effect, true, name + ': ' + JSON.stringify(results.agentguard_database));
    cases.push({ name, expected: { receipts: expected[0], cents: expected[1] }, results });
  }
  const { rows: [engine] } = await db.query('show server_version');
  console.log(JSON.stringify({
    mode: 'isolated in-memory database; synthetic USD ledger', engine: engine.server_version,
    migration_sha256_lf: hashes, sql_assertion_files_passed: sqlAssertions,
    matching_expected_effects: Object.fromEntries(models.map(model => [model, cases.filter(item => item.results[model].matches_expected_effect).length])),
    cases, limitations: [
      'The scope check in this comparison uses fixture identities, not OAuth tokens.',
      'The SQL assertions and full policy use the actual AgentGuard migrations; baseline behavior is illustrative.',
      'One in-memory PostgreSQL connection. No concurrency, real human review, live API, model, or payment is tested here.',
    ],
  }, null, 2));
} finally {
  await db.close();
}
