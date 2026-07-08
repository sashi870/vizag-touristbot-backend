const express = require("express");

const router = express.Router();

const Review =
    require("../models/Review");

router.post(
    "/submit-review",
    async(req,res)=>{

        try{

            const newReview =
                new Review(req.body);

            await newReview.save();

            res.json({
                success:true
            });

        }catch(error){

            res.status(500).json({
                success:false
            });
        }
    }
);

router.get(
    "/place-rating/:place",
    async(req,res)=>{

        try{

            const reviews =
                await Review.find({

                    place:req.params.place

                });

            if(reviews.length === 0){

                return res.json({

                    average:0,
                    total:0

                });
            }

            const totalRating =
                reviews.reduce(

                    (sum,item)=>
                        sum + item.rating,

                    0
                );

            const average =
                (
                    totalRating /
                    reviews.length
                ).toFixed(1);

            res.json({

                average,
                total:reviews.length

            });

        }catch(error){

            res.status(500).json({
                success:false
            });
        }
    }
);

module.exports = router;