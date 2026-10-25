import assert from 'node:assert/strict';
import test from 'node:test';

import { formatRouteDuration, VEHICLES_CONFIG } from './vehicleModes.js';

test('vehicle modes preserve backend route timings and delivery-window arrivals', () => {
  const route = {
    total_duration: 15,
    segments: [{ duration: 10, waiting_minutes: 5, estimated_arrival_time: '09:15 AM' }],
    arrival_times: { customer1: '09:15 AM' }
  };
  const deliveryWindow = { readyAfterMinutes: 10, dueByMinutes: 20 };

  for (const mode of ['scooter', 'bicycle']) {
    assert.ok(VEHICLES_CONFIG[mode]);
    assert.equal('etaMultiplier' in VEHICLES_CONFIG[mode], false);
    assert.equal(formatRouteDuration(route.total_duration), '15.0');
    assert.equal(formatRouteDuration(route.segments[0].duration), '10.0');
    assert.equal(route.segments[0].estimated_arrival_time, '09:15 AM');
    assert.equal(route.arrival_times.customer1, '09:15 AM');

    const arrivalOffsetMinutes = 15;
    assert.ok(arrivalOffsetMinutes >= deliveryWindow.readyAfterMinutes);
    assert.ok(arrivalOffsetMinutes <= deliveryWindow.dueByMinutes);
  }
});
