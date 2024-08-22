from visualization import PlotTrainingProgress, ProgressBar

import torch

class LossValues:
  def __init__(self):
    self.generator_loss_values = {}
    self.discriminator_loss_values = {}
    self.entropy_values = {}

def train_model(device, 
                num_epochs, 
                train_loader, 
                model_list,
                optimizer_list, 
                checkpoint_folder, 
                start_epoch=0,
                checkpoint_interval=5,
                training_mode='alternating',
                loss_values=LossValues()):
  from features import save_checkpoint
  
  if loss_values is None:
    loss_values = LossValues()

  # Setup models
  generator = model_list[0]
  optimizer_generator = optimizer_list[0]
  discriminator_list = model_list[1:]
  optimizer_discriminator_list = optimizer_list[1:]
  num_discriminators = len(discriminator_list)
  batch_size = train_loader.batch_size
  total_batches = len(train_loader)

  # Create instant for plotting 
  plot_progress = PlotTrainingProgress()

  # Training loop
  print(f'Start training at epoch {start_epoch}')
  for epoch in range(start_epoch, num_epochs):
    # Initialize tqdm progress bar
    progress_bar = ProgressBar(total_batches, epoch, num_epochs)
    
    for batch_i, (real_samples, mnist_labels) in enumerate(train_loader):
      # Data for training the discriminator
      real_samples = real_samples.to(device=device)
      real_samples_labels = torch.ones((train_loader.batch_size, 1)).to(device=device)
      latent_space_samples = torch.randn((train_loader.batch_size, 100)).to(device=device)
      generated_samples = generator(latent_space_samples)
      generated_samples_labels = torch.zeros((train_loader.batch_size, 1)).to(device=device)
      all_samples = torch.cat((real_samples, generated_samples))
      all_samples_labels = torch.cat((real_samples_labels, generated_samples_labels))

      # Training the discriminator
      for i, (discriminator, optimizer_discriminator) in enumerate(zip(discriminator_list, optimizer_discriminator_list)):
        discriminator.zero_grad()
        optimizer_discriminator.zero_grad()
        output_discriminator = discriminator(all_samples)
        loss_discriminator = discriminator.loss_function(output_discriminator, all_samples_labels)
        loss_discriminator.backward(retain_graph=True if i < num_discriminators - 1 else False)
        optimizer_discriminator.step()

        # Store discriminator loss for plotting
        if discriminator.name not in loss_values.discriminator_loss_values:
            loss_values.discriminator_loss_values[discriminator.name] = []
        loss_values.discriminator_loss_values[discriminator.name].append(loss_discriminator.cpu().detach().numpy())

      # Data for training the generator
      latent_space_samples = torch.randn((train_loader.batch_size, 100)).to(device=device)

      # Training the generator
      if training_mode == 'combined':
        generator.zero_grad()
        generated_samples = generator(latent_space_samples)
        combined_output = torch.zeros_like(discriminator(generated_samples))
        for i, discriminator in enumerate(discriminator_list):
            output_discriminator_generated = discriminator(generated_samples)
            combined_output += output_discriminator_generated
        combined_output /= len(discriminator_list)
        loss_generator = generator.loss_function(combined_output, real_samples_labels)
        loss_generator.backward()
        optimizer_generator.step()
      elif training_mode == 'alternating':
        for discriminator in discriminator_list:
          generator.zero_grad()
          generated_samples = generator(latent_space_samples)
          output_discriminator_generated = discriminator(generated_samples)
          loss_generator = generator.loss_function(output_discriminator_generated, real_samples_labels)
          loss_generator.backward()
          optimizer_generator.step()
      else:
        raise ValueError(f"Training mode {training_mode} not supported")

      # Store generator loss for plotting
      if generator.name not in loss_values.generator_loss_values:
        loss_values.generator_loss_values[generator.name] = []
      loss_values.generator_loss_values[generator.name].append(loss_generator.cpu().detach().numpy())

      # Manually update the progress bar
      progress_bar.update(1)

    # Update and Close the progress bar
    progress_bar_data = {'loss_G': f"{loss_values.generator_loss_values[generator.name][-1]:.5f}"}
    for i, discriminator in enumerate(loss_values.discriminator_loss_values.keys()):
      progress_bar_data[f'loss d_{i}'] = f"{loss_values.discriminator_loss_values[discriminator][-1]:.5f}"
    progress_bar.set_postfix(progress_bar_data)
    progress_bar.close()
        
    # Plot progress
    plot_progress.plot(epoch, num_epochs, loss_values)

    # Save checkpoint at the specified interval
    if (epoch + 1) % checkpoint_interval == 0:
      save_checkpoint(epoch, checkpoint_folder, model_list, optimizer_list, loss_values)    

  print('Training finished')

