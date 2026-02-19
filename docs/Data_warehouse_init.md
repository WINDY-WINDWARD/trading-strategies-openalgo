i want to build data archive with sql lite db. this data archive will be a seperate sub application as part of this app. the data archive will have its own folder structure, db and UI it will be completely independent from the current app
the data warehouse will store OHLCV data from open algo for specified companies.

it should have endpoints for 

Add Stock Data:
where a stock ticker is provided and time range is provided.
the app will make calls to openAlgo and fetch and store data.
if ticker data is already present and the range provided is already part of existing data return already present error
if ticker is present and time range is different from data provided then download the missing time range data from openAlgo
params: ticker, range(default 1 year from current date)

delete Stock Data:
as the name says. option to select time range to delete or all data
params: ticker, range(optional)

update Stock data:
fetch the last timestamp of stock data, then fetch data from openAlgo for data from last time stamp to latest.
param: ticker

get Stock data:
fetch stock data from the db to the requester.
params: ticker, range(default 1 year from current date).


Add Stock data (bulk):
same as add stock data.
params: csv file with headers -> ticker, range
process the tickers in batch