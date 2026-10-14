import assert from 'node:assert/strict';
import { test } from 'node:test';
import { navigationDestination, navigationGroup, settingsPages } from '../src/navigation';

test('desktop administration is a separate group, reserved for admins', () => {
  assert.equal(navigationGroup('admin'), 'admin');
  assert.equal(navigationDestination('admin', [], 'admin'), 'admin');
  assert.equal(navigationDestination('admin', [], 'user'), undefined);
  assert.equal(navigationDestination('admin', [], 'readonly'), undefined);
  assert.equal((settingsPages as readonly string[]).includes('admin'), false);
});
