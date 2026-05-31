-- SQLite
ALTER TABLE reservations ADD COLUMN heating_on BOOLEAN DEFAULT 0;
ALTER TABLE reservations ADD COLUMN lighting_on BOOLEAN DEFAULT 0;