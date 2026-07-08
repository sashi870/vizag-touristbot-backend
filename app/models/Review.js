const mongoose = require("mongoose");

const ReviewSchema = new mongoose.Schema({

    place:{
        type:String,
        required:true
    },

    rating:{
        type:Number,
        required:true
    },

    review:{
        type:String
    },

    createdAt:{
        type:Date,
        default:Date.now
    }

});

module.exports =
    mongoose.model(
        "Review",
        ReviewSchema
    );