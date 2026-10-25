export const VEHICLES_CONFIG = {
  scooter: { name: 'Moto (Scooter)', emoji: '🛵', costMultiplier: 1.0, desc: 'Two-wheel delivery display' },
  motorcycle: { name: 'Moto (Sports)', emoji: '🏍️', costMultiplier: 1.25, desc: 'Motorcycle delivery display' },
  bicycle: { name: 'Eco (Bicycle)', emoji: '🚲', costMultiplier: 0.5, desc: 'Bicycle delivery display' },
  auto: { name: 'Auto Rickshaw', emoji: '🛺', costMultiplier: 1.4, desc: 'Auto-rickshaw delivery display' },
  car: { name: 'Premium (Taxi)', emoji: '🚗', costMultiplier: 2.2, desc: 'Car delivery display' }
};

export const formatRouteDuration = (duration) => Number(duration).toFixed(1);
