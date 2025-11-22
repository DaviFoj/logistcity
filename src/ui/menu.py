import pygame
from pygame.locals import *
from sys import exit

pygame.init()

largura = 1280
altura = 720

running = True

tela = pygame.display.set_mode((largura, altura))
pygame.display.set_caption('Logitcity')

fps = pygame.time.Clock()

background = pygame.image.load('assets/background_menu.png').convert()
font = pygame.font.SysFont('assets/fonts/upheavtt.ttf', 32)

while running:
    fps.tick(60)
    for event in pygame.event.get():
        if event.type == QUIT:
            pygame.quit()
            exit()

    tela.blit(background, (0, 0))
    logo = pygame.image.load('assets/logo.png').convert_alpha()
    tela.blit(texto, (largura / 2 - texto.get_width() / 2, 50))

    pygame.display.update()