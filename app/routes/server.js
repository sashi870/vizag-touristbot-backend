const express = require("express");

const cors = require("cors");

const mongoose = require("mongoose");

const reviewRoutes =
    require("./backend/routes/reviewRoutes");

const app = express();

app.use(cors());

app.use(express.json());

app.use(
    "/api",
    reviewRoutes
);

mongoose.connect(

    "mongodb://127.0.0.1:27017/vizag-tourist-bot"

)
.then(()=>{

    console.log(
        "MongoDB Connected"
    );

})
.catch((err)=>{

    console.log(err);

});

app.listen(5000,()=>{

    console.log(
        "Server Running On Port 5000"
    );

});