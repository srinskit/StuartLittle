const express = require('express');
const path = require('path');
const fs = require('fs');
const cookieParser = require('cookie-parser');
const logger = require('morgan');
const RachServer = require('rach-server');

const app = express();

app.use(logger('dev'));
app.use(express.json());
app.use(express.urlencoded({extended: false}));
app.use(cookieParser());
app.use(express.static(path.join(__dirname, 'public')));

const bns_map = {};

app.get('/', function (req, res) {
    fs.readFile('./public/html/index.html', function (err, data) {
        res.writeHead(200, {'Content-Type': 'text/html', 'Content-Length': data.length});
        res.write(data);
        res.end();
    });
});

app.post('/stream', function (req, res) {
    try {
        let bot_name = req.body.bot_name;
        if (bot_name != null && bot_name.length > 0 && bns_map[bot_name] != null) {
            res.cookie('bot_ip', bns_map[bot_name], {maxAge: 900000, httpOnly: false});
            res.cookie('bot_name', bot_name, {maxAge: 900000, httpOnly: false});
            res.end();
        } else {
            res.locals.message = "Access denied";
            res.status(401);
            res.end();
        }
    } catch (e) {
        res.locals.message = "Access denied";
        res.status(401);
        res.end();
    }
});

app.get('/stream', function (req, res) {
    fs.readFile('./public/html/stream.html', function (err, data) {
        res.writeHead(200, {'Content-Type': 'text/html', 'Content-Length': data.length});
        res.write(data);
        res.end();
    });
});

app.post('/bns/register', function (req, res) {
    let bot_name = req.body.bot_name, bot_ip = req.ip;
    try {
        bot_ip = bot_ip.substr(7);
        if (bot_name.length > 0 && bot_ip.length > 0)
            bns_map[bot_name] = bot_ip;
    } catch (e) {

    } finally {
        res.end();
    }
});

// error handler
app.use(function (err, req, res, next) {
    res.locals.message = err.message;
    res.status(err.status || 500);
    res.end();
});

const services = {
    '/version':
        function (rach, client, on_err, on_result) {
            on_result('1.0');
        },
};
const actions = {
    authTest: function (cred) {
        return true;
    },
};

const rachServer = new RachServer(actions, services, console, 8080);
rachServer.addSub('/bots', function (data) {
    // console.info(data);
}, []);
rachServer.start();

module.exports = app;
