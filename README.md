([Ver en español](README-es.md))

# Net Balance Component for Home Assistant

## What is net balance?

In Spain and other countries, users of photovoltaic panels with surplus compensation have hourly net balance, which calculates the final result of import and export every hour and bills accordingly.

To put it simply: If you export 3 kWh and import 1 kWh in one hour, it will simply be considered that you have exported 2 kWh.

Since exporting is always cheaper than importing, this represents significant savings for the user.

### Example:

Let's assume that importing costs €0.15/kWh, and exporting gives a discount of €0.11/kWh. In the first case, we export 3 kWh and import 1 kWh, and in the second case, it's the opposite.

#### Without Balance
`1 * €0.15 - 3 * €0.11 = -€0.18`

`3 * €0.15 - 1 * €0.11 = €0.34`

#### With Balance
`1 - 3 = -2 => -2 * €0.11 = -€0.22`

`3 - 1 = 2 => 2 * €0.15 = €0.30`

As we can see, in both cases, net balance benefits the user.

## What does this component do?

This component calculates your current hourly balance as well as the result at the end of the hour.

To do this, you need to provide the total imported and exported kWh from your inverter, and the component will create three new entities:

- Net Import
- Net Export
- Current Hourly Balance

You can then use Net Import and Net Export in the Energy panel for Home Assistant to perform calculations correctly.

### Without net metering

![Without Balance](img/sin%20balance.png)

### With Balance

![With Balance](img/balance.png)

## Installation

You can install the component using HACS. To do this, simply add this repository to your custom repositories and search for "balance neto".

## Configuration

Once installed, go to _Devices and Services -> Add Integration_ and search for _Balance_.

The assistant will ask for 2 entities: total import from grid kWh and total exported to grid kWh.

## Usage

Once the component is configured, use "Net Import" as the sensor for _network consumption_ and "Net Export" for _network feed_.

>#### :warning: If you already have historical data in HA, changing the sensors will stop displaying old data. If you want to keep the data, you will need to connect to the database and copy/update the old import/export records to the net import and net export records.

## Activating Devices When There Are Surpluses

Thanks to the Current Hourly Balance entity, you can activate and deactivate high-consumption devices, such as electric water heaters, to make the most of the surpluses.

Instead of using power regulators to adjust consumption to your current production, you can turn the device on and off based on the balance value. For example, turn on the water heater/AC when the net balance is greater than 0.2 kWh and turn it off when it's less than -0.05 kWh.

This way, we can avoid reducing power when a cloud passes by temporarily or never turning on a 1500W device if our surpluses are 750W when we could have it on for half an hour without any issues.
