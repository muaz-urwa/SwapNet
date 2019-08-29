"""
A general framework for GAN training.
"""
from argparse import ArgumentParser
from abc import ABC, abstractmethod

import modules
import optimizers
from models import BaseModel
from modules.discriminators import Discriminator


class BaseGAN(BaseModel, ABC):
    @staticmethod
    def modify_commandline_options(parser: ArgumentParser, is_train):
        """
        Adds several GAN-related training arguments.
        Child classes should call
        >>> parser = super().modify_commandline_options(parser, is_train)
        """
        if is_train:
            parser.add_argument(
                "--gan_mode",
                help="gan regularization to use",
                default="meschder_r1",
                choices=("vanilla", "wgangp", "dragan", "mescheder_r1", "mescheder_r2"),
            )
            parser.add_argument(
                "--lambda_gan",
                type=float,
                default=1.0,
                help="weight for adversarial loss",
            )
            parser.add_argument(
                "--lambda_gp",
                help="weight parameter for gradient penalty",
                type=float,
                default=0.2,
            )
            # optimizer choice
            parser.add_argument(
                "--optimizer_G",
                help="optimizer for generator",
                choices=("AdamW", "AdaBound"),
            )
            parser.add_argument(
                "--optimizer_D",
                help="optimizer for discriminator",
                choices=("AdamW", "AdaBound"),
            )
            return parser

    def __init__(self, opt):
        """
        Sets the generator, discriminator, and optimizers.

        Sets self.generator to the return value of self.define_G()

        Args:
            opt:
        """
        super().__init__(opt)
        self.net_generator = self.define_G()
        if self.is_train:
            # setup discriminator
            self.net_discriminator = Discriminator(
                in_channels=self.get_D_inchannels(), img_size=self.opt.crop_size
            )

            # setup GAN loss
            self.criterion_GAN = modules.loss.GANLoss(opt.gan_mode).to(self.device)
            self.loss_names = ("D", "D_real", "D_fake", "D_gp", "G")

            # Define optimizers
            self.optimizer_G = optimizers.define_optimizer(
                self.net_generator.parameters(), opt, "G"
            )
            self.optimizer_D = optimizers.define_optimizer(
                self.net_discriminator.parameters(), opt, "D"
            )
            self.optimizer_names = ("G", "D")

    @abstractmethod
    def get_D_inchannels(self):
        """
        Return number of channels for discriminator input.
        Called when constructing the Discriminator network.
        """
        pass

    @abstractmethod
    def define_G(self):
        """
        Return the generator module. Called in init()
        The returned value is set to self.generator().
        """
        pass

    def optimize_parameters(self):
        self.forward()
        # update D
        self.optimizer_D.zero_grad()
        self.backward_D()
        self.optimizer_D.step()
        # update G
        self.optimizer_G.zero_grad()
        self.backward_G()
        self.optimizer_G.step()

    def backward_D(self):
        """
        Calculates loss and backpropagates for the discriminator
        """
        # calculate real
        pred_fake = self.net_discriminator(self.fakes.detach())
        self.loss_D_fake = self.criterion_GAN(pred_fake, False)
        # calculate fake
        pred_real = self.net_discriminator(self.targets)
        self.loss_D_real = self.criterion_GAN(pred_real, True)
        # calculate gradient penalty
        self.loss_D_gp = modules.loss.gradient_penalty(
            self.net_discriminator, self.targets, self.fake, self.opt.gan_mode
        )
        # final loss
        self.loss_D = (
            0.5 * (self.loss_D_fake + self.loss_D_real)
            + self.opt.lambda_gp * self.loss_D_gp
        )
        self.loss_D.backwards()

    @abstractmethod
    def backward_G(self):
        """
        Calculate loss and backpropagates for the generator
        """
        pass
